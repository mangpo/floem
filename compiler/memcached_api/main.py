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

Unpack = Element("Unpack",
                 [Port("in", ["cq_entry*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_item", ["item*"])],
                 r'''
(cq_entry* entry) = in();
output { out_opaque(entry->opaque); out_item(entry->it); }
                 ''')

PrintEntry = Element("PrintEntry",
                     [Port("in", ["eq_entry*"])],
                     [],
                     r'''
     (eq_entry* m) = in();
     printf("%ld %d %d\n", m->opaque, *((uint8_t *) m->key), m->hash);
     ''')

PrintMsg = Element("PrintMsg",
                   [Port("in", ["iokvs_message*"])],
                   [],
                   r'''
   (iokvs_message* m) = in();
   uint8_t *key = m->payload + 4;
   printf("%d %d %d\n", m->mcr.request.magic, m->mcr.request.bodylen, key[0]);
   ''')

(t_state, t_insert_element, t_get_element, t_state_instance, t_insert_instance, t_get_instance) = \
    get_table_collection("uint64_t", "iokvs_message*", 64, "msg_put", "msg_get")

p = Program(
    t_state, t_state_instance,
    State("eq_entry", "uint64_t opaque; uint32_t hash; uint16_t keylen; void* key;"),
    State("cq_entry", "uint64_t opaque; item* it;"),

    CircularQueue("RXQueue", "eq_entry*", 4),
    Jenkins_Hash, ForkPacket, ForkOpaque, GetKey,  Pack, GetOpaque, PrintEntry, PrintMsg,
    ElementInstance("PrintMsg", "print_msg"),
    ElementInstance("PrintEntry", "print_entry"),

    ElementInstance("ForkPacket", "fork_pkt"),
    ElementInstance("ForkOpaque", "fork_opaque"),
    ElementInstance("GetKey", "get_key"),
    ElementInstance("Jenkins_Hash", "hash"),
    ElementInstance("Pack", "rx_pack"),
    CompositeInstance("RXQueue", "rx_queue"),
    ElementInstance("GetOpaque", "get_opaque"),
    t_insert_element,t_get_element,  t_insert_instance, t_get_instance,
    Inject("iokvs_message*", "inject", 8, "random_request"),

    Connect("inject", "fork_pkt"),
    Connect("fork_pkt", "get_key", "out1"),
    Connect("get_key", "hash"),
    Connect("hash", "rx_pack", "out", "in_hash"),

    Connect("fork_pkt", "msg_put", "out2", "in_value"),
    Connect("fork_pkt", "get_opaque", "out3"),
    Connect("get_opaque", "fork_opaque"),
    Connect("fork_opaque", "msg_put", "out1", "in_index"),
    Connect("fork_opaque", "rx_pack", "out2", "in_opaque"),

    Connect("rx_pack", "rx_queue"),

    APIFunction("get_eq", "rx_queue", "dequeue", "rx_queue", "dequeue_out", "eq_entry*", "NULL"),

    CircularQueue("TXQueue", "cq_entry*", 4), Unpack, PrepareResponse,
    CompositeInstance("TXQueue", "tx_queue"),
    ElementInstance("Unpack", "unpack"),
    ElementInstance("PrepareResponse", "response"),

    Connect("tx_queue", "unpack"),
    Connect("unpack", "msg_get", "out_opaque"),
    Connect("msg_get", "response", "out", "in_packet"),
    Connect("unpack", "response", "out_item", "in_item"),
    Connect("response", "print_msg"),
    APIFunction("send_cq", "tx_queue", "enqueue", "tx_queue", "enqueue_out"),
    InternalTrigger("tx_queue", "dequeue"),
)


include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''


def run():
    testing = r'''
    '''
    depend = ['jenkins_hash', 'hashtable']
    dp = desugar(p)
    g = generate_graph(dp)
    generate_code_as_header(g, testing, include)
    compile_and_run("test", depend)


run()
