from dsl import *
from elements_library import *

eq_entry = create_state("eq_entry", "uint64_t opaque; uint32_t hash; uint16_t keylen; void* key;")
cq_entry = create_state("cq_entry", "uint64_t opaque; item* it;")

fork_pkt = create_fork_instance("fork_pkt", 3, "iokvs_message*")
fork_opaque = create_fork_instance("fork_opaque", 2, "uint64_t")
#fork_eq = create_fork_instance("fork_eq", 2, "eq_entry*")

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

# get_core = create_element_instance("GetCore",
#                  [Port("in", ["eq_entry*"])],
#                  [Port("out", ["size_t"])],
#                  r'''
# (eq_entry* entry) = in();
# output { out(entry->hash % 4); }  // reta[entry->key_hash & 0xff];
#                  ''')

print_msg = create_element_instance("print_msg",
                   [Port("in", ["iokvs_message*"])],
                   [],
                   r'''
   (iokvs_message* m) = in();
   uint8_t *key = m->payload + 4;
   printf("OPAQUE: %d, len: %d, key:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
   ''')

rx_queue = create_circular_queue_instance("rx_queue", "eq_entry*", 4)
tx_queue = create_circular_queue_instance("tx_queue", "cq_entry*", 4)
msg_put, msg_get = create_table_instances("msg_put", "msg_get", "uint64_t", "iokvs_message*", 64)
inject = create_inject_instance("inject", "iokvs_message*", 8, "random_request")

nic_rx = internal_thread("nic_rx")
get_eq = API_thread("get_eq", [], "eq_entry*", "NULL")
send_cq = API_thread("send_cq", ["cq_entry*"], None)
nic_tx = internal_thread("nic_tx")

# NIC RX
pkt = inject()
pkt1, pkt2, pkt3 = fork_pkt(pkt)       # TODO: automatically insert fork
opaque = get_opaque(pkt1)              # TODO: easier way to extract field
opaque1, opaque2 = fork_opaque(opaque)
msg_put(opaque1, pkt2)

key = get_key(pkt3)
hash = jenkins_hash(key)
eq_entry1 = pack(hash, opaque2)
eq_entry2 = rx_queue(eq_entry1)

nic_rx.run_start(inject, fork_pkt, get_opaque, fork_opaque, msg_put, get_key, jenkins_hash, pack)  # TODO: better way to assign threads. This is very error-proned.
rx_queue(None, nic_rx.run, get_eq.run_start)

# NIC TX
cq_entry = tx_queue(None)
opaque3, item = unpack(cq_entry)
pkt4 = msg_get(opaque3)
response = prepare_response(pkt4, item)
print_msg(response)

tx_queue(None, send_cq.run_start, nic_tx.run_start)
nic_tx.run(unpack, msg_get, prepare_response, print_msg)

c = Compiler()
c.include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.depend = ['jenkins_hash', 'hashtable']
c.triggers = True

def run_spec():
    c.generate_code_as_header("tmp_spec.h")
    c.compile_and_run("test")

run_spec()

