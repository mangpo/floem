from dsl import *
from elements_library import *
import queue

#eq_entry = create_state("eq_entry", "uint64_t opaque; uint32_t hash; uint16_t keylen; void* key;")
#cq_entry = create_state("cq_entry", "uint64_t opaque; item* it;")

classifier = create_element_instance("classifier",
              [Port("in", ["iokvs_message*"])],
              [Port("out_get", ["iokvs_message*"]), Port("out_set", ["iokvs_message*"])],
               r'''
(iokvs_message* m) = in();
uint8_t cmd = m->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get(m);
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set(m);
  // else drop
}
''')

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

make_eqe_get = create_element_instance("make_eqe_get",
               [Port("in_packet", ["iokvs_message*"]),
                Port("in_hash", ["void*", "size_t", "uint32_t"]), Port("in_opaque", ["uint64_t"])],
               [Port("out", ["eq_entry*"])],
               r'''
in_packet();
(void* key, size_t len, uint32_t hash) = in_hash();
(uint64_t opaque) = in_opaque();
eqe_rx_get* entry = (eqe_rx_get *) malloc(sizeof(eqe_rx_get));
entry->flags = EQE_TYPE_RXGET;
entry->opaque = opaque;
entry->hash = hash;
entry->keylen = len;
entry->key = key;
output { out(entry); }
               ''')
make_eqe_set = create_element_instance("make_eqe_set",
               [Port("in_item", ["item*"]), Port("in_opaque", ["uint64_t"])],
               [Port("out", ["eq_entry*"])],
               r'''
(item* it) = in_item();
(uint64_t opaque) = in_opaque();
eqe_rx_set* entry = (eqe_rx_set *) malloc(sizeof(eqe_rx_set));
entry->flags = EQE_TYPE_RXSET;
entry->opaque = opaque;
entry->item = it;
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

get_total_len = create_element_instance("get_total_len",
                   [Port("in", ["iokvs_message*"])],
                   [Port("out", ["size_t"])],
                   r'''
   (iokvs_message* m) = in();
   output { out(m->mcr.request.bodylen - m->mcr.request.extlen); }
   ''')

n_segments = 4
Segments = create_state("segments_holder",
                       "segment_header* segments[%d]; int head; int tail; int size;" % n_segments,
                       [[0],0,n_segments-1,n_segments])

segments = Segments()
get_item_creator = create_element("GetItem",
                   [Port("in", ["size_t"])],
                   [Port("out_item", ["item*"]), Port("out_full", ["bool"])],
                   r'''
    (size_t totlen) = in();
    bool full = false;
    item *it = segment_item_alloc(this.segments[this.head], totlen);
    if(it == NULL) {
        full = true;
        this.head = (this.head + 1) %s %d;
        // Assume that the next one is not full.
        it = segment_item_alloc(this.segments[this.head], totlen);
    }

    output {
        out_item(it);
        out_full(full);
    }
    ''' % ("%", n_segments), None, [("segments_holder", "this")])
get_item = get_item_creator("get_item", [segments])

fill_item = create_element_instance("fill_item",
                   [Port("in_item", ["item*"]),
                    Port("in_hash", ["void*", "size_t", "uint32_t"]), Port("in_totlen", ["size_t"])],
                   [Port("out", ["item*"])],
                   r'''
    (item* it) = in_item();
    (void* key, size_t keylen, uint32_t hash) = in_hash();
    (size_t totlen) = in_totlen();
    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    rte_memcpy(item_key(it), key, totlen);
    output { out(it); }
   ''')

msg_put, msg_get = create_table_instances("msg_put", "msg_get", "uint64_t", "iokvs_message*", 64)
Inject = create_inject("inject", "iokvs_message*", 8, "random_request")
inject = Inject()

n_cores = 4
nic_rx = internal_thread("nic_rx")
nic_tx = internal_thread("nic_tx")

######################## NIC Rx #######################
pkt = inject()
pkt_get, pkt_set = classifier(pkt)
hash = jenkins_hash(get_key(pkt))   # hash forks to both get request and set request case.
opaque = get_opaque(pkt)            # opaque forks to both get request and set request case.
msg_put(opaque, pkt)
nic_rx.run_start(inject, classifier, get_opaque, msg_put, get_key, jenkins_hash)

# Get request
eqe_get = make_eqe_get(pkt_get, hash, opaque)
nic_rx.run(make_eqe_get)

# Set request
total_len = get_total_len(pkt_set)
item, full = get_item(total_len)
item = fill_item(item, hash, total_len)
eqe_set = make_eqe_set(item, opaque)
nic_rx.run(get_total_len, get_item, fill_item, make_eqe_set)

# Full segment
nop = create_element_instance("nop", [Port("in", ["bool"])], [], "in();")  # TODO
nop(full)
nic_rx.run(nop)


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
nic2app(eqe_get)
nic2app(eqe_set)

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
#include "incif.h"
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


