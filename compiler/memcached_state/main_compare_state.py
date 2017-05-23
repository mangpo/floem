from dsl import *
from elements_library import *
import queue, queue_smart

n_cores = 4

save_state = create_element_instance("save_state",
                    [Port("in", ["iokvs_message*"])],
                    [Port("out", [])],
                    r'''
(iokvs_message* m) = in();
state.pkt = m;
output { out(); }
                    ''')

classifier = create_element_instance("classifier",
              [Port("in_pkt", [])],
              [Port("out_get", []),
               Port("out_set", [])],
               r'''
printf("receive id: %d\n", state.pkt->mcr.request.opaque);
uint8_t cmd = state.pkt->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get();
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set();
  // else drop
}
''')

get_key = create_element_instance("GetKey",
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.key = state.pkt->payload + state.pkt->mcr.request.extlen;
state.keylen = state.pkt->mcr.request.keylen;
//printf("keylen = %s\n", len);
output { out(); }
''' % '%ld')

get_core = create_element_instance("get_core",
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.core = state.hash %s %d;
output { out(); }
''' % ('%', n_cores))


######################## hash ########################

jenkins_hash = create_element_instance("Jenkins_Hash",
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.hash = jenkins_hash(state.key, state.pkt->mcr.request.keylen);
//printf("hash = %d\n", hash);
output { out(); }
''')

lookup = create_element_instance("Lookup",
              [Port("in", [])],
              [Port("out", [])],
               r'''
state.it = hasht_get(state.key, state.pkt->mcr.request.keylen, state.hash);
output { out(); }
''')

hash_put = create_element_instance("hash_put",
              [Port("in", [])],
              [Port("out", [])],
               r'''
hasht_put(state.it, NULL);
item_unref(state.it);
output { out(); }
''')

######################## responses ########################

prepare_get_response = create_element_instance("prepare_get_response",
                          [Port("in", [])],
                          [Port("out", ["iokvs_message*"])],
                          r'''
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + it->vallen);
item* it = state.it;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
m->mcr.request.magic = state.pkt->mcr.request.magic;
m->mcr.request.opaque = state.pkt->mcr.request.opaque;
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
                          [Port("in", [])],
                          [Port("out", ["iokvs_message*"])],
                          r'''
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.magic = state.pkt->mcr.request.magic;
m->mcr.request.opaque = state.pkt->mcr.request.opaque;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(m); }
''')

print_msg = create_element_instance("print_msg",
                   [Port("in", ["iokvs_message*"])],
                   [],
                   r'''
   (iokvs_message* m) = in();
   uint8_t *val = m->payload + 4;
   uint8_t opcode = m->mcr.request.opcode;
   if(opcode == PROTOCOL_BINARY_CMD_GET)
        printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.opaque, m->mcr.request.bodylen, val[0]);
   else if (opcode == PROTOCOL_BINARY_CMD_SET)
        printf("SET -- id: %d, len: %d\n", m->mcr.request.opaque, m->mcr.request.bodylen);
   ''')

######################## log segment #######################

filter_full = create_element_instance("filter_full",
               [Port("in", [])],
               [Port("out", [])],
               r'''
output switch { case state.segfull: out(full); }
               ''')

new_segment = create_element_instance("create_new_segment",
              [Port("in", [])],
              [Port("out", [])],
               r'''
struct segment_header* segment = new_segment(&ia, false);
if(segment == NULL) {
    printf("Fail to allocate new segment.\n");
    exit(-1);
}
state.segbase = segment->data;
state.seglen = segment->size;
output { out(); }
''')

Segments = create_state("segments_holder",
                        "uint64_t segbase; uint64_t seglen; uint64_t offset; struct _segments_holder* next;",
                        [0,0,0,0])
segments = Segments()

Last_segment = create_state("last_segment",
                        "struct _segments_holder* holder;",
                        [0])
last_segment = Last_segment()

add_logseg_creator = create_element("add_logseg_creator",
                   [Port("in", [])], [],
                   r'''
    if(this->segbase) {
        struct _segments_holder* holder = (struct _segments_holder*) malloc(sizeof(struct _segments_holder));
        holder->segbase = state.segbase;
        holder->seglen = state.seglen;
        holder->offset = 0;
        last->holder->next = holder;
        last->holder = holder;
    }
    else {
        this->segbase = state.segbase;
        this->seglen = state.seglen;
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
    ''', None, [("segments_holder", "this"), ("last_segment", "last")])
add_logseg = add_logseg_creator("add_logseg", [segments, last_segment])


######################## item ########################
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
           m->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = state.hash;
    it->vallen = totlen - state.pkt->mcr.request.keylen;
    it->keylen = state.pkt->mcr.request.keylen;
    //it->refcount = 1;
    rte_memcpy(item_key(it), state.key, totlen);
    state.it = it;
    state.segfull = full;

    output { out(); }
   ''', None, [("segments_holder", "this")])
get_item = get_item_creator("get_item", [segments])

get_item_spec = create_element_instance("get_item_spec",
                   [Port("in", [])],
                   [Port("out", [])],
                   r'''
    (iokvs_message* m) = in_pkt();
    (void* key, size_t keylen, uint32_t hash) = in_hash();
    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    item *it = (item *) malloc(sizeof(item) + totlen);

    //printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
             m->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    it->refcount = 1;
    rte_memcpy(item_key(it), key, totlen);
    state.it = it;

    output { out(); }
   ''')

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


########################## pipeline states #########################

mystate = create_state("mystate",
                       r'''
iokvs_message* pkt;
item* it @shared(data_region);
void* key @copysize(state.pkt->mcr.request.keylen);
uint64_t segfull;
uint64_t segbase;
uint64_t seglen;
                       ''')

iokvs_message = create_state("iokvs_message",
                             r'''
    protocol_binary_request_header mcr;
    uint8_t payload[];
                             ''', None, declare=False)

protocol_binary_request_header = create_state("protocol_binary_request_header",
                             r'''
            uint8_t magic;
            uint8_t opcode;
            uint16_t keylen;
            uint8_t extlen;
            uint8_t datatype;
            uint16_t status;
            uint32_t bodylen;
            uint32_t opaque;
            uint64_t cas;
                             ''', None, declare=False)


########################## program #########################
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
        pkt = save_state(pkt)
        pipeline_state(save_state, "mystate")
        pkt = get_key(pkt)
        pkt = jenkins_hash(pkt)
        pkt_hash_get, pkt_hash_set = classifier(pkt)

        # Get request
        item = lookup(pkt_hash_get)
        get_response = prepare_get_response(item)
        print_msg(probe_get(get_response))

        # Set request
        pkt = get_item_spec(pkt_hash_set)
        pkt = hash_put(pkt)
        set_response = prepare_set_response(pkt)
        print_msg(probe_set(set_response))


def impl():
    create_memory_region("data_region", 4 * 1024 * 512)

    # Queue
    rx_enq, rx_deq = queue_smart.smart_circular_queue_variablesize_one2many_instances(
        "rx_queue", 10000, n_cores, 3)
    tx_enq, tx_deq, tx_scan = queue_smart.smart_circular_queue_variablesize_many2one_instances(
        "queue", 10000, n_cores, 3, clean="enq")

    ######################## NIC Rx #######################

    @internal_trigger("nic_rx", process="nic")
    def rx_pipeline():
        # From network
        pkt = inject()
        pkt = save_state(pkt)
        pipeline_state(save_state, "mystate")
        pkt = jenkins_hash(get_key(pkt))
        pkt = get_core(pkt)
        pkt_get, pkt_set = classifier(pkt)

        pkt_item = get_item(pkt_set)
        full_segment = filter_full(pkt_item)  # Need this element

        rx_enq(pkt_get, pkt_item, full_segment)

    ######################## APP #######################

    @API("get_eq", process="app")
    def get_eq(core):
        pkt_get, pkt_set, full_segment = rx_deq(core)
        get_done = lookup(pkt_get)
        set_done = hash_put(pkt_set)
        segment_done = new_segment(full_segment)
        tx_enq(get_done, set_done, segment_done)

    @API("clean_cq", process="app")
    def clean_cq(core):
        get, set, full = tx_scan(core)
        get = unref(get)
        o = clean(get)
        o = clean(set)
        o = clean(full)
        return o

    ######################## NIC Tx #######################

    @internal_trigger("nic_tx", process="nic")
    def tx_pipeline():
        cqe_get, cqe_set, cqe_logseg = tx_deq()  # TODO: else case
        get_response = prepare_get_response(cqe_get)
        set_response = prepare_set_response(cqe_set)
        add_logseg(cqe_logseg)

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