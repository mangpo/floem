from dsl import *
from elements_library import *

Fork = create_fork("ForkPacket", 2, "iokvs_message*")
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

lookup = create_element_instance("Lookup",
              [Port("in", ["void*", "size_t", "uint32_t"])],
              [Port("out", ["item*"])],
               r'''
(void* key, size_t length, uint32_t hash) = in();
item *it = hasht_get(key, length, hash);
output { out(it); }
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

print_msg = create_element_instance("Print",
                [Port("in", ["iokvs_message*"])],
                [],
                r'''
(iokvs_message* m) = in();
uint8_t *key = m->payload + 4;
printf("%d %d %d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
''')

pkt1, pkt2 = Fork("fork_pkt")(None)
key = get_key(pkt1)
hash = jenkins_hash(key)
item = lookup(hash)
response = prepare_response(pkt2, item)
print_msg(response)

c = Compiler()
c.include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.testing = r'''
populate_hasht(10);
fork_pkt(random_request(1));
fork_pkt(random_request(2));
fork_pkt(random_request(3));
fork_pkt(random_request(100));
'''
c.depend = ['jenkins_hash', 'hashtable']
c.generate_code_and_run([1,5,3, 2,5,6, 3,5,9, 100,4,100])
