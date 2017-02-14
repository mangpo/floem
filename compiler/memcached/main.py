from compiler import *

ForkPacket = Fork("ForkPacket", 2, "iokvs_message*")

GetKey = Element("GetKey",
              [Port("in", ["iokvs_message*"])],
              [Port("out", ["void*", "size_t"])],
               r'''
(iokvs_message* m) = in();
void *key = m->paylod + m->mcr.request.extlen;
size_t len = m->mcr.request.keylen;
output { out(key, len); }''')

Jenkins_Hash = Element("Jenkins_Hash",
              [Port("in", ["void*", "size_t"])],
              [Port("out", ["void*", "size_t", "uint32_t"])],
               r'''
(void* key, uint32_t length) = in();
unit32_t hash = jenkins_hash(key, length);
output { out(key, length, hash); }''')

Lookup = Element("Lookup",
              [Port("in", ["void*", "size_t", "uint32_t"])],
              [Port("out", ["item*"])],
               r'''
(void* key, uint32_t length, unit32_t hash) = in();
// item *rdits = hasht_get(key, length, hash);
//item *rdits = NULL;
item *rdits = (item *) malloc(sizeof(item));
rdits->hv = hash;
rdits->keylen = 0;
output { out(rdits); }''')

PrepareResponse = Element("PrepareResponse",
                          [Port("in_packet", ["iokvs_message*"]), Port("in_item", ["item*"])],
                          [Port("out", ["iokvs_message*"])],
                          r'''
(iokvs_message* m) = in_packet();
(item* it) = in_item();
m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = htons(0);

m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
if (it != NULL) {
  m->mcr.request.bodylen = 4 + it->vallen;
  rte_memcpy(m->payload + 4, item_value(it), it->vallen);
}

output { out(m); }
''')


p = Program(
    Jenkins_Hash, Lookup, ForkPacket, GetKey, PrepareResponse,
    ElementInstance("ForkPacket", "fork"),
    ElementInstance("GetKey", "get_key"),
    ElementInstance("Jenkins_Hash", "hash"),
    ElementInstance("Lookup", "lookup"),
    ElementInstance("PrepareResponse", "response"),
    Connect("fork", "get_key", "out1"),
    Connect("fork", "response", "out2"),
    Connect("get_key", "hash"),
    Connect("hash", "lookup"),
    Connect("lookup", "response", "out", "in_item")
)