from dsl import *
from elements_library import *
import queue, queue_smart

n_cores = 4

classifier = create_element_instance("classifier",
              [Port("in_pkt", [])],
              [Port("out_get", []),
               Port("out_set", [])],
               r'''
printf("receive id: %d\n", state.pkt->mcr.request.magic);
uint8_t cmd = state.pkt->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get();
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set();
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
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.key = state.pkt->payload + state.pkt->mcr.request.extlen;
state.keylen = state.pkt->mcr.request.keylen;
//printf("keylen = %s\n", len);
output { out(); }
''' % '%ld')

jenkins_hash = create_element_instance("Jenkins_Hash",
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.hash = jenkins_hash(state.key, state.pkt->mcr.request.keylen);
state.core = state.hash %s %d;
//printf("hash = %s\n", hash);
output { out(); }
''' % ('%d', '%d', '%', n_cores))

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
(iokvs_message* p) = in_packet();
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + it->vallen);
(item* it) = in_item();
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
//m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.magic = p->mcr.request.magic;
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
(iokvs_message* p) = in_packet();
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
//m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.magic = p->mcr.request.magic;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(m); }
''')



filter_full = create_element_instance("filter_full",
               [Port("in", [])],
               [Port("out", [])],
               r'''
output switch { case state.full: out(full); }
               ''')


unpack_get = create_element_instance("unpack_get",
                 [Port("in", ["cqe_send_getresponse*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_item", ["item*"]), Port("out_entry", ["q_entry*"])],
                 r'''
cqe_send_getresponse* entry = (cqe_send_getresponse*) in(); // TODO
output { out_opaque(entry->opaque); out_item(get_pointer(entry->item)); out_entry((q_entry*) entry); }
                 ''')

unpack_set = create_element_instance("unpack_set",
                 [Port("in", ["cqe_send_setresponse*"])],
                 [Port("out_opaque", ["uint64_t"]), Port("out_entry", ["q_entry*"])],
                 r'''
cqe_send_setresponse* entry = (cqe_send_setresponse*) in(); // TODO
output { out_opaque(entry->opaque); out_entry((q_entry*) entry); }
                 ''')

save_state = create_element_instance("save_state",
                    [Port("in", ["iokvs_message*"])],
                    [Port("out", [])],
                    r'''
(iokvs_message* m) = in();
state.pkt = m;
output { out(); }
                    ''')

get_opaque = create_element_instance("get_opaque",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''
state.opaque = state.pkt->mcr.request.magic;
output { out(); }
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

######################## Log segment ##########################
Segments = create_state("segments_holder",
                        "uint64_t segbase; uint64_t seglen; uint64_t offset; struct _segments_holder* next;",
                        [0,0,0,0])
segments = Segments()

Last_segment = create_state("last_segment",
                        "struct _segments_holder* holder;",
                        [0])
last_segment = Last_segment()

get_item_creator = create_element("get_item_creator",
                   [Port("in", [])],
                   [Port("out", [])],
                   r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    item *it = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen); // TODO
    if(it == NULL) {
        printf("Segment is full.\n");
        full = this->segbase + this->offset;
        this->segbase = this->next->segbase;
        this->seglen = this->next->seglen;
        this->offset = this->next->offset;
        this->next = this->next->next;
        // Assume that the next one is not full.
        it = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen);
    }

    printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
           m->mcr.request.magic, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = state.hash;
    it->vallen = totlen - state.pkt->mcr.request.keylen;
    it->keylen = state.pkt->mcr.request.keylen;
    //it->refcount = 1;
    rte_memcpy(item_key(it), state.key, totlen);
    state.it = it;
    state.full = full;

    output { out(); }
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
    if(this->segbase) {
        struct _segments_holder* holder = (struct _segments_holder*) malloc(sizeof(struct _segments_holder));
        holder->segbase = e->segbase;
        holder->seglen = e->seglen;
        holder->offset = 0;
        last->holder->next = holder;
        last->holder = holder;
    }
    else {
        this->segbase = e->segbase;
        this->seglen = e->seglen;
        this->offset = 0;
        last->holder = this;
    }

    int count = 1;
    segments_holder* p = this;
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

msg_put_creator, msg_get_creator = create_table("msg_put_creator", "msg_get_creator", "uint64_t", "iokvs_message*", 500)
msg_put = msg_put_creator("msg_put")
msg_get_get = msg_get_creator("msg_get_get")
msg_get_set = msg_get_creator("msg_get_set")

Inject = create_inject("inject", "iokvs_message*", 1000, "random_request")
#Inject = create_inject("inject", "iokvs_message*", 1000, "double_set_request")
inject = Inject()

Probe = create_probe("probe", "iokvs_message*", 1010, "cmp_func")
probe_get = Probe()
probe_set = Probe()

def spec():
    @internal_trigger("all", "nic")
    def tx_pipeline(): # TODO
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
    create_memory_region("data_region", 4 * 1024 * 512)

    # Queue
    rx_enq, rx_deq = queue_smart.smart_circular_queue_variablesize_one2many_instances("rx_queue", 10000, n_cores, 3)
    tx_enq, tx_deq, tx_scan = queue_smart.smart_circular_queue_variablesize_many2one_instances("queue", 10000, n_cores, 3, clean="enq")

    @internal_trigger("nic_rx", process="nic")
    def rx_pipeline():
        # From network
        pkt = inject()
        pkt = save_state(pkt)
        pkt_id = get_opaque(pkt)
        msg_put(opaque, pkt_id)  # TODO
        pkt_hash_core = jenkins_hash(get_key(pkt))
        pkt_get, pkt_set = classifier(pkt_hash_core)

        pkt_item = get_item(pkt_set)
        full_segment = filter_full(pkt_item)  # Need this element

        rx_enq(pkt_get, pkt_item, full_segment)

    # Dequeue
    @API("get_eq", process="app")
    def get_eq(core):
        pkt_get, pkt_set, full_segment = rx_deq(core)
        get_done = lookup(pkt_get)
        set_done = hash_put(pkt_set)  # TODO
        segment_done = new_segment(full_segment)  # TODO
        tx_enq(get_done, set_done, segment_done)


    ######################## NIC Tx #######################

    # Queue
    unref = create_element_instance("unref",
                                    [Port("in", [])],
                                    [Port("out", [])],
                                    r'''
        item_unref(state.it);
        output { out(); }''')

    clean = create_element_instance("clean",
                                    [Port("in", [])],
                                    [Port("out", ["bool"])],
                                    r'''
        output { out(true); }''')

    @API("clean_cq", process="app")
    def clean_cq(core):
        get, set, full = tx_scan(core)
        get = unref(get)
        o = clean(get)
        o = clean(set)
        o = clean(full)
        return o

    @internal_trigger("nic_tx", process="nic")
    def tx_pipeline():
        cqe_get, cqe_set, cqe_logseg, cqe_nop = tx_deq()  # TODO: continue here

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
master_process("app")

######################## Run test #######################
c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
#include "../queue.h"
#include "../shm.h"
'''
c.depend = ['jenkins_hash', 'hashtable', 'ialloc']
c.triggers = True
c.I = '/home/mangpo/lib/dpdk-16.11/build/include'

def run_spec():
    c.desugar_mode = "spec"
    c.generate_code_as_header("test_spec")
    c.compile_and_run("test_spec")

def run_impl():
    c.desugar_mode = "impl"
    c.generate_code_as_header("test_impl")
    c.compile_and_run("test_impl")

def run_compare():
    c.desugar_mode = "compare"
    c.generate_code_as_header()
    c.compile_and_run(["test_compare_app", "test_compare_nic"])


#run_spec()
#run_impl()
run_compare()

# TODO: opague #

# TODO: proper initialization (run_threads_init: only run dequeue pipeline, run_threads: run dequeue and inject)
# TODO: queue -- owner bit & tail pointer update
# TODO: queue -- high order function

'''
item_unref >>>
hasht_put: item_unref (done)
main:
- item_unref before sending response ***
- clean_log after packet_loop (done)
- full segment case: call segment_item_free ***

item_ref >>>
hasht_get: item_ref (done)
hasht_put: item_ref (done)

----------
get_next_event: clean_cq: item_unref for getresponse (done)
execute_request_set: item_unref (done)
execute_segment_full: ialloc_nicsegment_full: segment_item_free (done)
'''