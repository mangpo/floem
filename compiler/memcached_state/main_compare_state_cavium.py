from dsl2 import *
import queue_smart2
from compiler import Compiler

n_cores = 4

class protocol_binary_request_header_request(State):
    magic = Field(Uint(8))
    opcode = Field(Uint(8))
    keylen = Field(Uint(16))
    extlen = Field(Uint(8))
    datatype = Field(Uint(8))
    status = Field(Uint(16))
    bodylen = Field(Uint(32))
    opaque = Field(Uint(32))
    cas = Field(Uint(64))

    # Tell compiler not to generate this struct because it's already declared in some other header file.
    def init(self): self.declare = False

class protocol_binary_request_header(State):
    request = Field(protocol_binary_request_header_request)

    def init(self): self.declare = False


class iokvs_message(State):
    mcr = Field(protocol_binary_request_header)
    payload = Field(Array(Uint(8)))

    def init(self): self.declare = False

class MyState(State):
    pkt = Field(Pointer(iokvs_message))
    it = Field('item*', shared='data_region')
    key = Field('void*', copysize='state.pkt->mcr.request.keylen')
    hash = Field(Uint(32))
    segfull = Field(Uint(64))
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    core = Field(Uint(16))

class Schedule(State):
    core = Field(Size)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field(Array('struct item_allocator*', n_cores))

class segments_holder(State):
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    offset = Field(Uint(64))
    next = Field('struct _segments_holder*')  # TODO
    last = Field('struct _segments_holder*')  # TODO

class main(Pipeline):
    state = PerPacket(MyState)

    class SaveState(Element):
        def configure(self):
            self.inp = Input(Pointer(iokvs_message))
            self.out = Output()

        def impl(self):
            self.run_c(r'''
(iokvs_message* m) = inp();
state.pkt = m;
output { out(); }
            ''')

    class Classifer(Element):
        def configure(self):
            self.inp = Input()
            self.out_get = Output()
            self.out_set = Output()

        def impl(self):
            self.run_c(r'''
printf("receive id: %d\n", state.pkt->mcr.request.opaque);
uint8_t cmd = state.pkt->mcr.request.opcode;

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get();
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set();
  // else drop
}
            ''')

    class GetKey(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.key = state.pkt->payload + state.pkt->mcr.request.extlen;
//state.keylen = state.pkt->mcr.request.keylen;
//printf("keylen = %s\n", len);
output { out(); }''')

    class GetCore(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.core = state.hash %s %d;
output { out(); }''' % ('%', n_cores))

    ######################## hash ########################

    class JenkinsHash(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.hash = jenkins_hash(state.key, state.pkt->mcr.request.keylen);
//printf("hash = %d\n", hash);
output { out(); }
            ''')

    class HashGet(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.it = hasht_get(state.key, state.pkt->mcr.request.keylen, state.hash);
output { out(); }
            ''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
hasht_put(state.it, NULL);
output { out(); }
            ''')


    ######################## responses ########################

    class Scheduler(Element):
        this = Persistent(Schedule)

        def configure(self):
            self.out = Output(Size)
            self.this = Schedule()

        def impl(self):
            self.run_c(r'''
this->core = (this->core + 1) %s %s;
output { out(this->core); }''' % ('%', n_cores))

    class PrepareGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Pointer(iokvs_message))

        def impl(self):
            self.run_c(r'''
item* it = state.it;
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + it->vallen);
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
  memcpy(m->payload + 4, item_value(it), it->vallen);
}

output { out(m); }
            ''')  # TODO: free

        def impl_cavium(self):
            self.run_c(r'''
item* it = state.it;
uint32_t vallen = my_htonl(it->vallen);
iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + vallen);
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
  m->mcr.request.bodylen = 4 + vallen;
  void* kv;
  dma_read((uintptr_t) item_value(it), vallen, kv);
  memcpy(m->payload + 4, kv, vallen);
  dma_free(kv);
}

output { out(m); }
                        ''')  # TODO: free

    class PrepareSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Pointer(iokvs_message))

        def impl(self):
            self.run_c(r'''
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

    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(Pointer(iokvs_message))

        def impl(self):
            self.run_c(r'''
(iokvs_message* m) = inp();
uint8_t *val = m->payload + 4;
uint8_t opcode = m->mcr.request.opcode;
if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.opaque, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- id: %d, len: %d\n", m->mcr.request.opaque, m->mcr.request.bodylen);
free(m);
    ''')

    ######################## log segment #######################

    item_allocators = ItemAllocators()

    class FilterFull(ElementOneInOut):
        def impl(self):
            self.run_c(r'''output switch { case state.segfull: out(); }''')


    class FirstSegment(Element):
        this = Persistent(ItemAllocators)
        def states(self): self.this = main.item_allocators

        def configure(self):
            self.inp = Input(Size, 'struct item_allocator*')
            self.out = Output()

        def impl(self):
            self.run_c(r'''
(size_t core, struct item_allocator* ia) = inp();
this->ia[core] = ia;
state.core = core;
state.segbase = get_pointer_offset(ia->cur->data);
state.seglen = ia->cur->size;
output { out(); }
            ''')


    class NewSegment(ElementOneInOut):
        this = Persistent(ItemAllocators)
        def states(self): self.this = main.item_allocators

        def impl(self):
            self.run_c(r'''
struct segment_header* segment = new_segment(this->ia[state.core], false);
if(segment == NULL) {
    printf("Fail to allocate new segment.\n");
    exit(-1);
}
state.segbase = get_pointer_offset(segment->data);
state.seglen = segment->size;
ialloc_nicsegment_full(state.segfull);
output { out(); }
            ''')

    segments = segments_holder()

    class AddLogseg(Element):
        this = Persistent(segments_holder)

        def configure(self):
            self.inp = Input()
            self.this = main.segments

        def impl(self):
            self.run_c(r'''
    if(this->last != NULL) {
        //printf("this (before): %u, base = %u\n", this, this->segbase);
        struct _segments_holder* holder = (struct _segments_holder*) malloc(sizeof(struct _segments_holder));
        holder->segbase = state.segbase;
        holder->seglen = state.seglen;
        holder->offset = 0;
        this->last->next = holder;
        this->last = holder;
        //printf("this (after): %u, base = %u\n", this, this->segbase);
    }
    else {
        this->segbase = state.segbase;
        this->seglen = state.seglen;
        this->offset = 0;
        this->last = this;
    }

    int count = 1;
    segments_holder* p = this;
    while(p->next != NULL) {
        count++;
        p = p->next;
    }
    printf("addlog: new->segbase = %ld, cur->segbase = %ld\n", state.segbase, this->segbase);
    printf("logseg count = %d\n", count);
            ''')

    ######################## item ########################

    class GetItem(ElementOneInOut):
        this = Persistent(segments_holder)
        def states(self): self.this = main.segments

        def impl(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    printf("item_alloc: segbase = %ld\n", this->segbase);
    item *it = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen); // TODO
    if(it == NULL) {
        printf("Segment is full.\n");
        full = this->segbase + this->offset;
        this->segbase = this->next->segbase;
        this->seglen = this->next->seglen;
        this->offset = this->next->offset;
        //free(this->next);
        this->next = this->next->next;
        // Assume that the next one is not full.
        it = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen);
    }
    it->refcount = 1;

    printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
           state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = state.hash;
    it->vallen = totlen - state.pkt->mcr.request.keylen;
    it->keylen = state.pkt->mcr.request.keylen;
    memcpy(item_key(it), state.key, totlen);
    state.it = it;
    state.segfull = full;

    output { out(); }
                ''')

        def impl_cavium(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    printf("item_alloc: segbase = %ld\n", this->segbase);
    void* addr = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen); // TODO
    if(addr == NULL) {
        printf("Segment is full.\n");
        full = this->segbase + this->offset;
        this->segbase = this->next->segbase;
        this->seglen = this->next->seglen;
        this->offset = this->next->offset;
        //free(this->next);
        this->next = this->next->next;
        // Assume that the next one is not full.
        addr = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen);
    }
    item *it;
    dma_read((uintptr_t) addr, sizeof(item), (void**) &it);
    it->refcount = my_ntohs(1);

    printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
           state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = my_ntohl(state.hash);
    it->vallen = my_ntohl(totlen - state.pkt->mcr.request.keylen);
    it->keylen = my_ntohs(state.pkt->mcr.request.keylen);
    memcpy(item_key(it), state.key, totlen);
    dma_write((uintptr_t) addr, sizeof(item) + totlen, it);
    dma_free(it);

    state.it = addr;
    state.segfull = full;

    output { out(); }
            ''')

    class GetItemSpec(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    item *it = (item *) malloc(sizeof(item) + totlen);

    //printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
    //         state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
    it->hv = state.hash;
    it->vallen = totlen - state.pkt->mcr.request.keylen;
    it->keylen = state.pkt->mcr.request.keylen;
    it->refcount = 1;
    memcpy(item_key(it), state.key, totlen);
    state.it = it;

    output { out(); }
            ''')

    class Unref(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
        item_unref(state.it);
        output { out(); }
            ''')

    class Clean(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Bool)

        def impl(self):
            self.run_c(r'''output { out(true); }''')

    Inject = create_inject("inject", "iokvs_message*", 1000, "random_request")
    # Inject = create_inject("inject", "iokvs_message*", 1000, "double_set_request")
    Probe = create_probe("probe", "iokvs_message*", 1010, "cmp_func")


    ########################## program #########################
    def spec(self):
        class nic(InternalLoop):
            def impl(self):
                classifier = main.Classifer()
                display = main.PrintMsg()

                main.Inject() >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> classifier
                # get
                classifier.out_get >> main.HashGet() >> main.PrepareGetResp() >> main.Probe() >> display
                # set
                classifier.out_set >> main.GetItemSpec() >> main.HashPut() >> main.PrepareSetResp() >> main.Probe() \
                >> display

        nic('nic', process='nic')

    def impl(self):
        MemoryRegion('data_region', 4 * 1024 * 512)

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 10000, n_cores, 3)
        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 10000, n_cores, 3, clean="enq")
        rx_enq = RxEnq()
        rx_deq = RxDeq()
        tx_enq = TxEnq()
        tx_deq = TxDeq()
        tx_scan = TxScan()

        ######################## NIC Rx #######################
        class nic_rx(InternalLoop):
            def impl(self):
                classifier = main.Classifer()
                main.Inject() >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> main.GetCore() >> classifier

                # get
                classifier.out_get >> rx_enq.inp[0]
                # set
                get_item = main.GetItem()
                classifier.out_set >> get_item >> rx_enq.inp[1]
                # full
                get_item >> main.FilterFull() >> rx_enq.inp[2]

        ######################## APP #######################
        class process_eq(API):
            def configure(self):
                self.inp = Input(Size)

            def impl(self):
                self.inp >> rx_deq
                # get
                rx_deq.out[0] >> main.HashGet() >> tx_enq.inp[0]
                # set
                rx_deq.out[1] >> main.HashPut() >> main.Unref() >> tx_enq.inp[1]
                # full
                rx_deq.out[2] >> main.NewSegment() >> tx_enq.inp[2]

        class init_segment(API):
            def configure(self):
                self.inp = Input(Size)

            def impl(self):
                self.inp >> main.FirstSegment() >> tx_enq.inp[2]

        class clean_cq(API):
            def configure(self):
                self.inp = Input(Size)
                self.out = Output(Bool)
                self.default_return = 'false'

            def impl(self):
                clean = main.Clean()
                self.inp >> tx_scan
                # get
                tx_scan.out[0] >> main.Unref() >> clean

                tx_scan.out[1] >> clean
                tx_scan.out[2] >> clean
                clean >> self.out

        ####################### NIC Tx #######################
        class nic_tx(InternalLoop):
            def impl(self):
                display = main.PrintMsg()
                main.Scheduler() >> tx_deq
                # get
                tx_deq.out[0] >> main.PrepareGetResp() >> main.Probe() >> display
                # set
                tx_deq.out[1] >> main.PrepareSetResp() >> main.Probe() >> display
                # full
                tx_deq.out[2] >> main.AddLogseg()

        nic_rx('nic_rx', device=target.CAVIUM, cores=[1])
        process_eq('process_eq', process='app')
        init_segment('init_segment', process='app')
        clean_cq('clean_cq', process='app')
        nic_tx('nic_tx', device=target.CAVIUM, cores=[2])

master_process('app')

# NIC: ['jenkins_hash', 'ialloc']
# APP: ['jenkins_hash', 'hashtable', 'ialloc', 'nic']


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.generate_code_as_header()