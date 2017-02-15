from compiler import *
from desugaring import desugar
from standard_elements import *

ForkPacket = Fork("ForkPacket", 3, "iokvs_message*")
ForkOpaque = Fork("ForkOpaque", 2, "uint64_t")

GetKey = Element("GetKey",
              [Port("in", ["iokvs_message*"])],
              [Port("out", ["void*", "size_t"])],
               r'''
(iokvs_message* m) = in();
void *key = m->payload + m->mcr.request.extlen;
size_t len = m->mcr.request.keylen;
output { out(key, len); }
''')

Jenkins_Hash = Element("Jenkins_Hash",
              [Port("in", ["void*", "size_t"])],
              [Port("out", ["void*", "size_t", "uint32_t"])],
               r'''
(void* key, size_t length) = in();
uint32_t hash = jenkins_hash(key, length);
output { out(key, length, hash); }
''')


PrepareResponse = Element("PrepareResponse",
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

GetOpaque = Element("GetOpaque",
                    [Port("in", ["iokvs_message*"])],
                    [Port("out", ["uint64_t"])],
                    r'''
(iokvs_message* m) = in();
output { out(m->mcr.request.magic); }
                    ''')

Pack = Element("Pack",
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

Print = Element("Print",
                [Port("in", ["eq_entry*"])],
                [],
                r'''
(eq_entry* m) = in();
printf("%ld %d %d\n", m->opaque, *((uint8_t *) m->key), m->hash);
''')

(t_state, t_insert_element, t_get_element, t_state_instance, t_insert_instance, t_get_instance) = \
    get_table_collection("uint64_t", "iokvs_message*", 64, "msg_put", "msg_get")

p = Program(
    t_state, t_state_instance,
    State("eq_entry", "uint64_t opaque; uint32_t hash; uint16_t keylen; void* key;"),
    Jenkins_Hash, ForkPacket, ForkOpaque, GetKey, CircularQueue("Queue", "eq_entry*", 4), Pack, GetOpaque, Print,

    ElementInstance("ForkPacket", "fork"),
    ElementInstance("ForkOpaque", "fork_opaque"),
    ElementInstance("GetKey", "get_key"),
    ElementInstance("Jenkins_Hash", "hash"),
    ElementInstance("Pack", "rx_pack"),
    CompositeInstance("Queue", "rx_queue"),
    ElementInstance("GetOpaque", "get_opaque"),
    t_insert_element,t_get_element,  t_insert_instance, t_get_instance,
    ElementInstance("Print", "print"),

    Connect("fork", "get_key", "out1"),
    Connect("get_key", "hash"),
    Connect("hash", "rx_pack", "out", "in_hash"),

    Connect("fork", "msg_put", "out2", "in_value"),
    Connect("fork", "get_opaque", "out3"),
    Connect("get_opaque", "fork_opaque"),
    Connect("fork_opaque", "msg_put", "out1", "in_index"),
    Connect("fork_opaque", "rx_pack", "out2", "in_opaque"),

    Connect("rx_pack", "rx_queue"),

    APIFunction("extract_request", "rx_queue", "dequeue", "rx_queue", "out", "eq_entry*"),
)

testing = r'''
fork(random_request(1));
fork(random_request(2));
fork(random_request(3));

print(extract_request());
print(extract_request());
print(extract_request());

fork(random_request(101));
fork(random_request(102));
print(extract_request());
print(extract_request());
'''

include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''

depend = ['jenkins_hash']

expect = ['1', '1', '82610235', '2', '2', '-544296261', '3', '3', '-1151292978', '101', '101', '1187334374', '102', '102', '-1276648593']

dp = desugar(p)
g = generate_graph(dp)
#generate_code_with_test(g, testing, include)
generate_code_and_run(g, testing, expect, include, depend)
