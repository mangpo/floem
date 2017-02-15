from compiler import *
from desugaring import desugar

ForkPacket = Fork("ForkPacket", 2, "iokvs_message*")

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

Lookup = Element("Lookup",
              [Port("in", ["void*", "size_t", "uint32_t"])],
              [Port("out", ["item*"])],
               r'''
(void* key, size_t length, uint32_t hash) = in();
item *it = hasht_get(key, length, hash);
output { out(it); }
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

Print = Element("Print",
                [Port("in", ["iokvs_message*"])],
                [],
                r'''
(iokvs_message* m) = in();
uint8_t *key = m->payload + 4;
printf("%d %d %d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
''')

# Cons: c code has global object (hash table), but the framework has no idea about it.

p = Program(
    Jenkins_Hash, Lookup, ForkPacket, GetKey, PrepareResponse, Print,
    ElementInstance("ForkPacket", "fork"),
    ElementInstance("GetKey", "get_key"),
    ElementInstance("Jenkins_Hash", "hash"),
    ElementInstance("Lookup", "lookup"),
    ElementInstance("PrepareResponse", "response"),
    ElementInstance("Print", "print"),

    Connect("fork", "get_key", "out1"),
    Connect("fork", "response", "out2", "in_packet"),
    Connect("get_key", "hash"),
    Connect("hash", "lookup"),
    Connect("lookup", "response", "out", "in_item"),
    Connect("response", "print"),
)

testing = r'''
populate_hasht(10);
fork(random_request(1));
fork(random_request(2));
fork(random_request(3));
fork(random_request(100));
'''

include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''

depend = ['jenkins_hash', 'hashtable']

expect = [1,5,3, 2,5,6, 3,5,9, 100,4,100]

dp = desugar(p)
g = generate_graph(dp)
generate_code_with_test(g, testing, include)
generate_code_and_run(g, testing, expect, include, depend)
