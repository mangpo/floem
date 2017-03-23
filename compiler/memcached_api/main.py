from dsl import *
from elements_library import *
import queue

classifier = create_element_instance("classifier",
              [Port("in_pkt", ["iokvs_message*"]), Port("in_hash", ["void*", "size_t", "uint32_t"])],
              [Port("out_get", ["iokvs_message*", "void*", "size_t", "uint32_t"]),
               Port("out_set", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               r'''
(iokvs_message* m) = in_pkt();
(void* key, size_t len, uint32_t hash) = in_hash();
uint8_t cmd = m->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get(m, key, len, hash);
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set(m, key, len, hash);
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
  rte_memcpy(m->payload + 4, item_value(it), it->vallen);
}

output { out(m); }
''')

make_eqe_get = create_element_instance("make_eqe_get",
               [Port("in_pkt_hash", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               [Port("out", ["eq_entry*"])],
               r'''
(iokvs_message* m, void* key, size_t len, uint32_t hash) = in_pkt_hash();
eqe_rx_get* entry = (eqe_rx_get *) malloc(sizeof(eqe_rx_get));
entry->flags = EQE_TYPE_RXGET;
entry->opaque = m->mcr.request.magic;
entry->hash = hash;
entry->keylen = len;
entry->key = key;
output { out((eq_entry*) entry); }
               ''')

make_eqe_set = create_element_instance("make_eqe_set",
               [Port("in", ["item*", "uint64_t"])],
               [Port("out", ["eq_entry*"])],
               r'''
(item* it, uint64_t opaque) = in();
eqe_rx_set* entry = (eqe_rx_set *) malloc(sizeof(eqe_rx_set));
entry->flags = EQE_TYPE_RXSET;
entry->opaque = opaque;
entry->item = it;
output { out((eq_entry*) entry); }
               ''')

unpack = create_element_instance("Unpack",
                 [Port("in", ["cqe_send_getresponse*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_item", ["item*"])],
                 r'''
cqe_send_getresponse* entry = (cqe_send_getresponse*) in(); // TODO
output { out_opaque(entry->opaque); out_item(entry->item); }
                 ''')

get_opaque = create_element_instance("GetOpaque",
                    [Port("in", ["iokvs_message*"])],
                    [Port("out", ["uint64_t"])],
                    r'''
(iokvs_message* m) = in();
output { out(m->mcr.request.magic); }
                    ''')

print_msg = create_element_instance("print_msg",
                   [Port("in", ["iokvs_message*"])],
                   [],
                   r'''
   (iokvs_message* m) = in();
   uint8_t *key = m->payload + 4;
   printf("OPAQUE: %d, len: %d, key:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
   ''')


get_core = create_element("get_core",
                                       [Port("in", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
                                       [Port("out", ["size_t"])],
                                       r'''
    (iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in();
    output { out(hash % 4); }
                                       ''')
get_core_get = get_core("get_core_get")
get_core_set = get_core("get_core_set")

######################## Log segment ##########################
Segments = create_state("segments_holder",
                        "struct segment_header* segment; struct _segments_holder* next;",
                        [0,0])
segments = Segments()

Last_segment = create_state("last_segment",
                        "struct _segments_holder* holder;",
                        [0])
last_segment = Last_segment()

get_item_creator = create_element("get_item_creator",
                   [Port("in", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
                   [Port("out_item", ["item*", "uint64_t"]), Port("out_full", ["bool"])],
                   r'''
    (iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in();
    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    bool full = false;
    item *it = segment_item_alloc(this.segment, totlen);
    if(it == NULL) {
        full = true;
        this.segment = this.next->segment;
        this.next = this.next->next;
        // Assume that the next one is not full.
        it = segment_item_alloc(this.segment, totlen);
    }

    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    rte_memcpy(item_key(it), key, totlen);

    output { out_item(it, m->mcr.request.magic); out_full(full); }
   ''', None, [("segments_holder", "this")])
get_item = get_item_creator("get_item", [segments])

add_logseg_creator = create_element("add_logseg_creator",
                   [Port("in", ["cqe_add_logseg*"])], [],
                   r''''
    (cqe_add_logseg* e) = in();
    if(this.segment != NULL) {
        struct _segments_holder* holder = (struct _segments_holder*) malloc(sizeof(struct _segments_holder*));
        holder->segment = e->segment;
        last.holder->next = holder;
        last.holder = holder;
    }
    else {
        this.segment = e->segment;
        last.holder = &this;
    }
    ''', None, [("segments_holder", "this"), ("last_segment", "last")])
add_logseg = add_logseg_creator("add_logseg", [segments, last_segment])


######################## Rx ##########################
classifier_rx = create_element_instance("classifier_rx",
              [Port("in", ["cq_entry*"])],
              [Port("out_get", ["cqe_send_getresponse*"]), Port("out_logseg", ["cqe_add_logseg*"])],
               r'''
(cq_entry* e) = in();
uint16_t flags = e->flags;

output switch{
  case (flags == CQE_TYPE_GRESP): out_get((cqe_send_getresponse*) e);
  case (flags == CQE_TYPE_LOG): out_logseg((cqe_add_logseg*) e);
  // else drop
}
''')

msg_put, msg_get = create_table_instances("msg_put", "msg_get", "uint64_t", "iokvs_message*", 64)
Inject = create_inject("inject", "iokvs_message*", 8, "random_request")
inject = Inject()

n_cores = 4
nic_rx = internal_thread("nic_rx")
nic_tx = internal_thread("nic_tx")

######################## NIC Rx #######################
pkt = inject()
opaque = get_opaque(pkt)
msg_put(opaque, pkt)
hash = jenkins_hash(get_key(pkt))
pkt_hash_get, pkt_hash_set = classifier(pkt, hash)

nic_rx.run_start(inject, get_opaque, msg_put, get_key, jenkins_hash, classifier)

# Get request
eqe_get = make_eqe_get(pkt_hash_get)
eqe_get_core = get_core_get(pkt_hash_get)  # TODO
nic_rx.run(make_eqe_get, get_core_get)

# Set request
item_opaque, is_segment_full = get_item(pkt_hash_set)
eqe_set = make_eqe_set(item_opaque)
eqe_set_core = get_core_set(pkt_hash_set)  # TODO
nic_rx.run(get_item, make_eqe_set, get_core_set)

# Full segment
nop = create_element_instance("nop", [Port("in", ["bool"])], [], "in();")  # TODO
nop(is_segment_full)
nic_rx.run(nop)

# TODO: 1. initialize segments
# TODO: 2. use ialloc_from_offset and ialloc_to_offset (eq_entry contains item instead of item*)
# TODO: 3. circular queue stores entries instead of pointers to entries

def spec_nic2app(x, core):
    Drop = create_drop("Drop", "uint64_t")
    drop = Drop()
    drop(core)

    rx_enq, rx_deq = queue.create_circular_queue_instances("rx_queue_spec", "eq_entry*", 4)
    rx_enq(x)
    nic_rx.run(rx_enq, drop)

    #get_eq = API_thread("get_eq", [], "eq_entry*", "NULL")
    #get_eq.run_start(rx_deq)
    @API("get_eq", "NULL")
    def get_eq():
        return rx_deq()

def impl_nic2app(x, core):
    rx_enq, rx_deqs = queue.create_circular_queue_one2many_instances("rx_queue_impl", "eq_entry*", 4, n_cores)
    rx_enq(x, core)

    nic_rx.run(rx_enq)
    for i in range(n_cores):
        # api = API_thread("get_eq" + str(i), [], "eq_entry*", "NULL")
        # api.run_start(rx_deqs[i])
        @API("get_eq" + str(i), "NULL")
        def get_eq():
            return rx_deqs[i]()

nic2app = create_spec_impl("nic2app", spec_nic2app, impl_nic2app)
nic2app(eqe_get, eqe_get_core)
nic2app(eqe_set, eqe_set_core)

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
cqe_set, cqe_logseg = classifier_rx(cq_entry)

# get response
opaque, item = unpack(cqe_set)
pkt4 = msg_get(opaque)
response = prepare_response(pkt4, item)
nic_tx.run(unpack, msg_get, prepare_response)

# logseg
add_logseg(cqe_logseg)
nic_tx.run(add_logseg)

# print
print_msg(response)
nic_tx.run(print_msg)

######################## Run test #######################
c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.depend = ['jenkins_hash', 'hashtable', 'ialloc']
c.triggers = True
c.I = '/home/mangpo/lib/dpdk-16.11/build/include'

def run_spec():
    c.desugar_mode = "spec"
    c.generate_code_as_header("tmp_spec.h")
    c.compile_and_run("test")

def run_impl():
    c.desugar_mode = "impl"
    c.generate_code_as_header("tmp_impl.h")
    c.compile_and_run("test_impl")

#run_spec()
run_impl()


