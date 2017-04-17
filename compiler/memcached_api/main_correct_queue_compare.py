from dsl import *
from elements_library import *
import queue

n_cores = 4

classifier = create_element_instance("classifier",
              [Port("in_pkt", ["iokvs_message*"]), Port("in_hash", ["void*", "size_t", "uint32_t"])],
              [Port("out_get", ["iokvs_message*", "void*", "size_t", "uint32_t"]),
               Port("out_set", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               r'''
(iokvs_message* m) = in_pkt();
printf("receive id: %d\n", m->mcr.request.magic);
(void* key, size_t len, uint32_t hash) = in_hash();
uint8_t cmd = m->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get(m, key, len, hash);
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set(m, key, len, hash);
  // else drop
}
''')

extract_pkt_hash = create_element("extract_pkt_hash",
              [Port("in", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
              [Port("out_pkt", ["iokvs_message*"]),
               Port("out_hash", ["void*", "size_t", "uint32_t"])],
               r'''
(iokvs_message* m, void* key, size_t len, uint32_t hash) = in();

output {
  out_pkt(m);
  out_hash(key, len, hash);
}
''')
extract_pkt_hash_get = extract_pkt_hash()
extract_pkt_hash_set = extract_pkt_hash()

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

insert_item = create_element_instance("insert_item",
              [Port("in", ["item*"])],
              [],
               r'''
(item *it) = in();
hasht_put(it, NULL);
''')

# print_hash = create_element_instance("print_hash",
#               [Port("in", ["void*", "size_t", "uint32_t"])],
#               [],
#                r'''
# (void* key, size_t length, uint32_t hash) = in();
# printf("hash = %d\n", hash);
# ''')

prepare_get_response = create_element_instance("prepare_get_response",
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

prepare_set_response = create_element_instance("prepare_set_response",
                          [Port("in_packet", ["iokvs_message*"])],
                          [Port("out", ["iokvs_message*"])],
                          r'''
(iokvs_message* m) = in_packet();
// m->mcr.request.magic = PROTOCOL_BINARY_RES; // same
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(m); }
''')

len_get = create_element_instance("len_get",
               [Port("in_pkt_hash", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               [Port("out", ["size_t"])],
               r'''
(iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in_pkt_hash();
size_t len = sizeof(eqe_rx_get) + keylen;
output { out(len); }
               ''')

fill_eqe_get = create_element_instance("fill_eqe_get",
               [Port("in_entry", ["q_entry*"]), Port("in_pkt_hash", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               [Port("out", ["q_entry*"])],
               r'''
(iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in_pkt_hash();
eqe_rx_get* entry = (eqe_rx_get *) in_entry();
if(entry) {
    entry->flags |= EQE_TYPE_RXGET << EQE_TYPE_SHIFT;
    entry->opaque = m->mcr.request.magic;
    entry->hash = hash;
    entry->keylen = keylen;
    //entry->key = key;
    rte_memcpy(entry->key, key, keylen);
}
output switch { case entry: out((q_entry*) entry); }
               ''')

len_set = create_element_instance("len_set",
               [Port("in_pkt_hash", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
               [Port("out", ["size_t"])],
               r'''
(iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in_pkt_hash();
size_t len = sizeof(eqe_rx_set);
output { out(len); }
               ''')

fill_eqe_set = create_element_instance("fill_eqe_set",
               [Port("in_entry", ["q_entry*"]), Port("in_item", ["item*", "uint64_t"])],
               [Port("out", ["q_entry*"])],
               r'''
eqe_rx_set* entry = (eqe_rx_set *) in_entry();
(item* it, uint64_t opaque) = in_item();
//printf("make_eqe_set: opaque = %ld, refcount = %d, entry = %ld\n", opaque, it->refcount, entry);
if(entry) {
    entry->flags |= EQE_TYPE_RXSET << EQE_TYPE_SHIFT;
    entry->opaque = opaque;
    entry->item = it;
}
output switch { case entry: out((q_entry*) entry); }
               ''')


filter_full = create_element_instance("filter_full",
               [Port("in_segment", ["struct segment_header*"])],
               [Port("out", ["struct segment_header*"])],
               r'''
(struct segment_header* full) = in_segment();
output switch { case full: out(full); }
               ''')

len_core_full = create_element_instance("len_core_set",
               [Port("in_segment", ["struct segment_header*"])],
               [Port("out_len", ["size_t"]), Port("out_core", ["size_t"])],
               r'''
(struct segment_header* full) = in_segment();
size_t len = sizeof(eqe_seg_full);
output { out_len(len); out_core(0); }
               ''')

fill_eqe_full = create_element_instance("fill_eqe_full",
               [Port("in_entry", ["q_entry*"]), Port("in_segment", ["struct segment_header*"])],
               [Port("out", ["q_entry*"])],
               r'''
eqe_seg_full* entry = (eqe_seg_full *) in_entry();
(struct segment_header* full) = in_segment();
if(full) {
    entry->flags |= EQE_TYPE_SEGFULL << EQE_TYPE_SHIFT;
    entry->segment = full;
}
output switch { case full: out((q_entry*) entry); }
               ''')

len_cqe = create_element_instance("len_cqe",
               [Port("in", ["uint8_t"])],
               [Port("out", ["size_t"])],
               r'''
(uint8_t t) = in();
size_t len = 0;
switch(t) {
    case CQE_TYPE_GRESP: len = sizeof(cqe_send_getresponse); break;
    case CQE_TYPE_SRESP: len = sizeof(cqe_send_setresponse); break;
    case CQE_TYPE_LOG: len = sizeof(cqe_add_logseg); break;
}
output { out(len); }
               ''')

# fill_cqe(entry, type, pointer, opague)
fill_cqe = create_element_instance("fill_cqe",
               [Port("in_entry", ["q_entry*"]), Port("in_type", ["uint8_t"]),
                Port("in_pointer", ["void*"]), Port("in_opaque", ["uint64_t"])],
               [Port("out", ["q_entry*"])],
               r'''
(q_entry* e) = in_entry();
(uint8_t t) = in_type();
(void* p) = in_pointer();
(uint64_t opaque) = in_opaque();
if(e) {
    //printf("fill_cqe (1): entry = %ld, len = %ld\n", e, e->len);
    e->flags |= (uint16_t) t << CQE_TYPE_SHIFT;
    //printf("fill_cqe (2): entry = %ld, len = %ld\n", e, e->len);

    if(t == CQE_TYPE_GRESP) {
        cqe_send_getresponse* es = (cqe_send_getresponse*) e;
        es->opaque = opaque;
        es->item = p;
    }
    else if(t == CQE_TYPE_SRESP) {
        cqe_send_setresponse* es = (cqe_send_setresponse*) e;
        es->opaque = opaque;
    }
    else if(t == CQE_TYPE_LOG) {
        cqe_add_logseg* es = (cqe_add_logseg*) e;
        es->segment = p;
    //printf("fill_cqe (3): entry = %ld, len = %ld\n", e, e->len);
    }
}

    //printf("fill_cqe (4): entry = %ld, len = %ld\n", e, e->len);
output switch { case e: out(e); }
''')

unpack_get = create_element_instance("unpack_get",
                 [Port("in", ["cqe_send_getresponse*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_item", ["item*"]), Port("out_entry", ["q_entry*"])],
                 r'''
cqe_send_getresponse* entry = (cqe_send_getresponse*) in(); // TODO
output { out_opaque(entry->opaque); out_item(entry->item); out_entry((q_entry*) entry); }
                 ''')

unpack_set = create_element_instance("unpack_set",
                 [Port("in", ["cqe_send_setresponse*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_entry", ["q_entry*"])],
                 r'''
cqe_send_setresponse* entry = (cqe_send_setresponse*) in(); // TODO
output { out_opaque(entry->opaque); out_entry((q_entry*) entry); }
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
   uint8_t *val = m->payload + 4;
   uint8_t opcode = m->mcr.request.opcode;
   if(opcode == PROTOCOL_BINARY_CMD_GET)
        printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, val[0]);
   else if (opcode == PROTOCOL_BINARY_CMD_SET)
        printf("SET -- id: %d, len: %d\n", m->mcr.request.magic, m->mcr.request.bodylen);
   ''')

get_core = create_element("get_core",
                                       [Port("in", ["iokvs_message*", "void*", "size_t", "uint32_t"])],
                                       [Port("out", ["size_t"])],
                                       r'''
    (iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in();
    output { out(hash %s %d); }''' % ('%', n_cores))
get_core_get = get_core("get_core_get")
get_core_set = get_core("get_core_set")

# get_core_full = create_element_instance("get_core_full",
#                    [Port("in", ["eq_entry*"])],
#                    [Port("out", ["size_t"])],
#                    r'''
#    (eq_entry* e) = in();
#    output { out(0); }
#    ''')


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
                   [Port("out_item", ["item*", "uint64_t"]), Port("out_full", ["struct segment_header*"])],
                   r'''
    (iokvs_message* m, void* key, size_t keylen, uint32_t hash) = in();
    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    struct segment_header* full = NULL;
    item *it = segment_item_alloc(this.segment, sizeof(item) + totlen); // TODO
    if(it == NULL) {
        printf("Segment is full.\n");
        full = this.segment;
        this.segment = this.next->segment;
        this.next = this.next->next;
        // Assume that the next one is not full.
        it = segment_item_alloc(this.segment, sizeof(item) + totlen);
    }

    printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n", m->mcr.request.magic, keylen, hash, totlen, it);
    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    //it->refcount = 1;
    rte_memcpy(item_key(it), key, totlen);

    output { out_item(it, m->mcr.request.magic); out_full(full); }
   ''', None, [("segments_holder", "this")])
get_item = get_item_creator("get_item", [segments])

get_item_spec = create_element_instance("get_item_spec",
                   [Port("in_pkt", ["iokvs_message*"]), Port("in_hash", ["void*", "size_t", "uint32_t"])],
                   [Port("out", ["item*"])],
                   r'''
    (iokvs_message* m) = in_pkt();
    (void* key, size_t keylen, uint32_t hash) = in_hash();
    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    item *it = (item *) malloc(sizeof(item) + totlen);

    //printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n", m->mcr.request.magic, keylen, hash, totlen, it);
    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    it->refcount = 1;
    rte_memcpy(item_key(it), key, totlen);

    output { out(it); }
   ''')

add_logseg_creator = create_element("add_logseg_creator",
                   [Port("in", ["cqe_add_logseg*"])], [Port("out", ["q_entry*"])],
                   r'''
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

    int count = 1;
    segments_holder* p = &this;
    while(p->next != NULL) {
        count++;
        p = p->next;
    }
    printf("logseg count = %d\n", count);
    output { out((q_entry*) e); }
    ''', None, [("segments_holder", "this"), ("last_segment", "last")])
add_logseg = add_logseg_creator("add_logseg", [segments, last_segment])


######################## Rx ##########################
classifier_rx = create_element_instance("classifier_rx",
              [Port("in", ["q_entry*"])],
              [Port("out_get", ["cqe_send_getresponse*"]),
               Port("out_set", ["cqe_send_setresponse*"]),
               Port("out_logseg", ["cqe_add_logseg*"]),
               Port("out_nop", ["q_entry*"])],
               r'''
(q_entry* e) = in();
uint8_t type = CQE_TYPE_NOP;
if(e) {
    type = (e->flags & CQE_TYPE_MASK) >> CQE_TYPE_SHIFT;
}

output switch{
  case (type == CQE_TYPE_GRESP): out_get((cqe_send_getresponse*) e);
  case (type == CQE_TYPE_SRESP): out_set((cqe_send_setresponse*) e);
  case (type == CQE_TYPE_LOG): out_logseg((cqe_add_logseg*) e);
  case e: out_nop(e);
}
''')

msg_put_creator, msg_get_creator = create_table("msg_put_creator", "msg_get_creator", "uint64_t", "iokvs_message*", 256)
msg_put = msg_put_creator("msg_put")
msg_get_get = msg_get_creator("msg_get_get")
msg_get_set = msg_get_creator("msg_get_set")

Inject = create_inject("inject", "iokvs_message*", 1000, "random_request")
inject = Inject()

Probe = create_probe("probe", "iokvs_message*", 1010, "cmp_func")
probe_get = Probe()
probe_set = Probe()

def spec():
    @internal_trigger("all")
    def tx_pipeline():
        # From network
        pkt = inject()
        key = get_key(pkt)
        hash = jenkins_hash(key)
        pkt_hash_get, pkt_hash_set = classifier(pkt, hash)

        # Get request
        pkt, hash = extract_pkt_hash_get(pkt_hash_get)
        item = lookup(hash)
        get_response = prepare_get_response(pkt, item)
        print_msg(probe_get(get_response))

        # Set request
        pkt, hash = extract_pkt_hash_set(pkt_hash_set)
        item = get_item_spec(pkt, hash)
        insert_item(item)
        set_response = prepare_set_response(pkt)
        print_msg(probe_set(set_response))


def impl():
    ######################## NIC Rx #######################

    # Queue
    rx_enq_alloc_creator, rx_enq_submit_creator, rx_deq_get_creator, rx_deq_release_creator = \
        queue.create_circular_queue_variablesize_one2many("rx_queue", 1024, n_cores)
    enq_alloc_get = rx_enq_alloc_creator("enq_alloc_get")
    enq_alloc_set = rx_enq_alloc_creator("enq_alloc_set")
    enq_alloc_full = rx_enq_alloc_creator("enq_alloc_full")
    rx_enq_submit = rx_enq_submit_creator()
    rx_deq_get = rx_deq_get_creator()
    rx_deq_release = rx_deq_release_creator()

    @internal_trigger("nic_rx")
    def tx_pipeline():
        # From network
        pkt = inject()
        opaque = get_opaque(pkt)  # TODO: opaque = count
        msg_put(opaque, pkt)
        hash = jenkins_hash(get_key(pkt))
        pkt_hash_get, pkt_hash_set = classifier(pkt, hash)

        # Get request
        length = len_get(pkt_hash_get)
        core = get_core_get(pkt_hash_get)
        eqe_get = enq_alloc_get(length, core)
        eqe_get = fill_eqe_get(eqe_get, pkt_hash_get)
        rx_enq_submit(eqe_get)

        # Set request
        length = len_set(pkt_hash_set)
        core = get_core_set(pkt_hash_set)
        item_opaque, full_segment = get_item(pkt_hash_set)
        eqe_set = enq_alloc_set(length, core)
        eqe_set = fill_eqe_set(eqe_set, item_opaque)
        rx_enq_submit(eqe_set)

        # Full segment
        full_segment = filter_full(full_segment)  # Need this element
        length, core = len_core_full(full_segment)
        eqe_full = enq_alloc_full(length, core)
        eqe_full = fill_eqe_full(eqe_full, full_segment)
        rx_enq_submit(eqe_full)

    # Dequeue
    @API("get_eq")
    def get_eq(core):
        return rx_deq_get(core)

    @API("release")
    def release(x):
        rx_deq_release(x)

    ######################## NIC Tx #######################

    # Queue
    tx_enq_alloc, tx_enq_submit, tx_deq_get, tx_deq_release = \
        queue.create_circular_queue_variablesize_many2one_instances("tx_queue", 1024, n_cores)  # TODO: create just one enq/deq, take core_id as parameter.

    # Enqueue
    @API("send_cq")
    def send_cq(core, type, pointer, opague):
        length = len_cqe(type)
        entry = tx_enq_alloc(core, length)
        entry = fill_cqe(entry, type, pointer, opague)
        tx_enq_submit(entry)

    @internal_trigger("nic_tx")
    def tx_pipeline():
        cq_entry = tx_deq_get()
        cqe_get, cqe_set, cqe_logseg, cqe_nop = classifier_rx(cq_entry)

        # get response
        opaque, item, cqe_get = unpack_get(cqe_get)
        tx_deq_release(cqe_get)  # dependency
        pkt = msg_get_get(opaque)
        get_response = prepare_get_response(pkt, item)

        # set response
        opaque, cqe_set = unpack_set(cqe_set)
        tx_deq_release(cqe_set)  # dependency
        pkt = msg_get_set(opaque)
        set_response = prepare_set_response(pkt)

        # logseg
        cqe_logseg = add_logseg(cqe_logseg)
        tx_deq_release(cqe_logseg)  # dependency

        # nop
        tx_deq_release(cqe_nop)

        # print
        print_msg(probe_get(get_response))
        print_msg(probe_set(set_response))

memcached = create_spec_impl("memcached", spec, impl)

######################## Run test #######################
c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
#include "../queue.h"
'''
c.depend = ['jenkins_hash', 'hashtable', 'ialloc']
c.triggers = True
c.I = '/home/mangpo/lib/dpdk-16.11/build/include'

def run_spec():
    c.desugar_mode = "spec"
    c.generate_code_as_header("tmp_impl_correct_queue_spec.h")
    c.compile_and_run("test_impl_correct_queue_spec")

def run_impl():
    c.desugar_mode = "impl"
    c.generate_code_as_header("tmp_impl_correct_queue.h")
    c.compile_and_run("test_impl_correct_queue")

def run_compare():
    c.desugar_mode = "compare"
    c.generate_code_as_header("tmp_impl_correct_queue_compare.h")
    c.compile_and_run("test_impl_correct_queue_compare")


#run_spec()
#run_impl()
run_compare()

# TODO: opague #
# TODO: get rid of t.start()

# TODO: proper initialization (run_threads_init: only run dequeue pipeline, run_threads: run dequeue and inject)
# TODO: queue -- owner bit & tail pointer update
# TODO: queue -- high order function