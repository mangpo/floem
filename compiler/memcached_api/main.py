from dsl import *
from elements_library import *
import queue

eq_entry = create_state("eq_entry", "uint64_t opaque; uint32_t hash; uint16_t keylen; void* key;")
cq_entry = create_state("cq_entry", "uint64_t opaque; item* it;")

get_key = create_element_instance("GetKey",
              [Port("in", ["iokvs_message*"])],
              [Port("out", ["void*", "size_t"])],
               r'''
(iokvs_message* m) = in();
void *key = m->payload + m->mcr.request.extlen;
size_t len = m->mcr.request.keylen;
output { out(key, len); }
''')

jenkins_hash = create_element_instance("Jenkins_Hash",
              [Port("in", ["void*", "size_t"])],
              [Port("out", ["void*", "size_t", "uint32_t"])],
               r'''
(void* key, size_t length) = in();
uint32_t hash = jenkins_hash(key, length);
output { out(key, length, hash); }
''')

prepare_response = create_element_instance("PrepareResponse",
                          [Port("in_packet", ["iokvs_message*"]), Port("in_item", ["item*"])],
                          [Port("out", ["iokvs_message*"])],
                          r'''
(iokvs_message* m) = in_packet();
(item* it) = in_item();
// m->mcr.request.magic = PROTOCOL_BINARY_RES; // same
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
if (it != NULL) {
  m->mcr.request.bodylen = 4 + it->vallen;
  memcpy(m->payload + 4, item_value(it), it->vallen);
}

output { out(m); }
''')

pack = create_element_instance("Pack",
               [Port("in_hash", ["void*", "size_t", "uint32_t"]), Port("in_opaque", ["uint64_t"])],
               [Port("out", ["eq_entry*"])],
               r'''
(void* key, size_t len, uint32_t hash) = in_hash();
(uint64_t opaque) = in_opaque();
eq_entry* entry = (eq_entry *) malloc(sizeof(eq_entry));
entry->opaque = opaque;
entry->hash = hash;
entry->keylen = len;
entry->key = key;
output { out(entry); }
               ''')

unpack = create_element_instance("Unpack",
                 [Port("in", ["cq_entry*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_item", ["item*"])],
                 r'''
(cq_entry* entry) = in();
output { out_opaque(entry->opaque); out_item(entry->it); }
                 ''')

get_opaque = create_element_instance("GetOpaque",
                    [Port("in", ["iokvs_message*"])],
                    [Port("out", ["uint64_t"])],
                    r'''
(iokvs_message* m) = in();
output { out(m->mcr.request.magic); }
                    ''')

GetCore = create_element("GetCore",
                 [Port("in", ["eq_entry*"])],
                 [Port("out", ["size_t"])],
                 r'''
(eq_entry* entry) = in();
output { out(entry->hash % 4); }  // reta[entry->key_hash & 0xff];
                 ''')

print_msg = create_element_instance("print_msg",
                   [Port("in", ["iokvs_message*"])],
                   [],
                   r'''
   (iokvs_message* m) = in();
   uint8_t *key = m->payload + 4;
   printf("OPAQUE: %d, len: %d, key:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
   ''')


msg_put, msg_get = create_table_instances("msg_put", "msg_get", "uint64_t", "iokvs_message*", 64)
Inject = create_inject("inject", "iokvs_message*", 8, "random_request")
inject = Inject()

n_cores = 4
nic_rx = internal_thread("nic_rx")
nic_tx = internal_thread("nic_tx")

######################## NIC Rx #######################
pkt = inject()
opaque = get_opaque(pkt)              # TODO: easier way to extract field
msg_put(opaque, pkt)
hash = jenkins_hash(get_key(pkt))
eq_entry = pack(hash, opaque)

nic_rx.run_start(inject, get_opaque, msg_put, get_key, jenkins_hash, pack)

def spec_nic2app(x):
    rx_enq, rx_deq = queue.create_circular_queue_instances("rx_queue_spec", "eq_entry*", 4)
    rx_enq(x)
    nic_rx.run(rx_enq)

    #get_eq = API_thread("get_eq", [], "eq_entry*", "NULL")
    #get_eq.run_start(rx_deq)
    @API("get_eq", "NULL")
    def get_eq():
        return rx_deq()

def impl_nic2app(x):
    get_core = GetCore()
    rx_enq, rx_deqs = queue.create_circular_queue_one2many_instances("rx_queue_impl", "eq_entry*", 4, n_cores)

    rx_enq(x, get_core(x))

    nic_rx.run(get_core, rx_enq)
    for i in range(n_cores):
        # api = API_thread("get_eq" + str(i), [], "eq_entry*", "NULL")
        # api.run_start(rx_deqs[i])
        @API("get_eq" + str(i), "NULL")
        def get_eq():
            return rx_deqs[i]()

nic2app = create_spec_impl("nic2app", spec_nic2app, impl_nic2app)
nic2app(eq_entry)

######################## NIC Tx #######################

def spec_app2nic():
    tx_enq, tx_deq = queue.create_circular_queue_instances("tx_queue_spec", "cq_entry*", 4)
    y = tx_deq()

    send_cq = API_thread("send_cq", ["cq_entry*"], None)
    send_cq.run_start(tx_enq)
    nic_tx.run_start(tx_deq)
    return y

def impl_app2nic():
    tx_enqs, tx_deq = queue.create_circular_queue_many2one_instances("tx_queue_impl", "cq_entry*", 4, n_cores)
    y = tx_deq()

    for i in range(n_cores):
        api = API_thread("send_cq" + str(i), ["cq_entry*"], None)
        api.run_start(tx_enqs[i])
    nic_tx.run_start(tx_deq)
    return y

app2nic = create_spec_impl("app2nic", spec_app2nic, impl_app2nic)

cq_entry = app2nic()
opaque3, item = unpack(cq_entry)
pkt4 = msg_get(opaque3)
response = prepare_response(pkt4, item)
print_msg(response)

nic_tx.run(unpack, msg_get, prepare_response, print_msg)

######################## Run test #######################
c = Compiler()
c.include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.depend = ['jenkins_hash', 'hashtable']
c.triggers = True

def run_spec():
    c.desugar_mode = "spec"
    c.generate_code_as_header("tmp_spec.h")
    c.compile_and_run("test")

def run_impl():
    c.desugar_mode = "impl"
    c.generate_code_as_header("tmp_impl.h")
    c.compile_and_run("test_impl")

run_spec()
run_impl()

