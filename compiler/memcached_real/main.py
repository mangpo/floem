from dsl2 import *
import queue_smart2, net_real
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
    pkt_buff = Field('void*')
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
    next = Field('struct _segments_holder*')
    last = Field('struct _segments_holder*')

class main(Pipeline):
    state = PerPacket(MyState)

    class SaveState(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")
            self.out = Output()

        def impl(self):
            self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
state.pkt = (iokvs_message*) pkt;
state.pkt_buff = buff;
output { out(); }
            ''')

    class CheckPacket(Element):
        def configure(self):
            self.inp = Input(Size, 'void*', 'void*')
            self.out = Output(Size, 'void*', 'void*')
            self.slowpath = Output( 'void*', 'void*')
            self.drop = Output('void*', 'void*')

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;

int type; // 0 = normal, 1 = slow, 2 = drop

if (m->ether.ether_type == htons(ETHER_TYPE_IPv4) &&
    m->ipv4.next_proto_id == 17 &&
    m->ipv4.dst_addr == settings.localip &&
    m->udp.dst_port == htons(11211) &&
    msglen >= sizeof(iokvs_message))
{
    uint32_t blen = ntohl(m->mcr.request.bodylen);
    uint32_t keylen = ntohs(m->mcr.request.keylen);

        /* Ensure request is complete */
        if (blen < keylen + m->mcr.request.extlen ||
            msglen < sizeof(iokvs_message) + blen) {
            type = 2;
        }
        else if (m->mcudp.n_data != htons(1)) {
            type = 2;
        }
        else if (m->mcr.request.opcode != PROTOCOL_BINARY_CMD_GET &&
                 m->mcr.request.opcode != PROTOCOL_BINARY_CMD_SET) {
            type = 2;
        }
        else {
            type = 0;
        }
} else {
  type = 1;
}

output switch {
    case type==0: out(msglen, m, buff);
    case type==1: slowpath(m, buff);
    else: drop(m, buff);
}
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

    class HashGet(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.null = Output()

        def impl(self):
            self.run_c(r'''
Item* it = hasht_get(state.key, state.pkt->mcr.request.keylen, state.hash);
state.it = it;
output switch { case it: out(); else: null(); }
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
            self.out = Output(Size, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
        iokvs_message *m = state.pkt;
        int msglen = sizeof(iokvs_message) + 4;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        item* it = state.it;
        m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_SUCCESS);

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = htonl(4);
*((uint32_t *)m->payload) = 0;
msglen += it->vallen;
m->mcr.request.bodylen = htonl(4 + it->vallen);
rte_memcpy(m->payload + 4, item_value(it), it->vallen);

void* pkt_buff = state.pkt_buff;

output { out(msglen, m, pkt_buff); }
            ''')

    class PrepareGetNullResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
            iokvs_message *m = state.pkt;
            int msglen = sizeof(iokvs_message) + 4;

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_KEY_ENOENT);

    m->mcr.request.keylen = 0;
    m->mcr.request.extlen = 4;
    m->mcr.request.bodylen = htonl(4);
    *((uint32_t *)m->payload) = 0;
    void* pkt_buff = state.pkt_buff;

    output { out(msglen, m, pkt_buff); }
                ''')


    class PrepareSetResp(Element):
        def configure(self, status):
            self.inp = Input()
            self.out = Output(Size, Pointer(iokvs_message), 'void*')
            self.status = status
            # PROTOCOL_BINARY_RESPONSE_SUCCESS
            # PROTOCOL_BINARY_RESPONSE_ENOMEM

        def impl(self):
            self.run_c(r'''
iokvs_message *m = state.pkt;
int msglen = sizeof(iokvs_message) + 4;

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = htons(%s);

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

void* pkt_buff = state.pkt_buff;

output { out(msglen, m, pkt_buff); }
            ''' % self.status)




    class PrepareHeader(Element):
        def configure(self):
            self.inp = Input(Size, Pointer(iokvs_message), "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
        (size_t msglen, iokvs_message* m, void* buff) = inp();
        struct ether_addr mymac = m->ether.d_addr;

        m->ether.d_addr = m->ether.s_addr;
        m->ether.s_addr = mymac; // TODO: mymac
        m->ipv4.dst_addr = m->ipv4.src_addr;
        m->ipv4.src_addr = settings.localip;
        m->ipv4.total_length = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4.time_to_live = 64;
        m->ipv4.hdr_checksum = 0;
        //m->ipv4.hdr_checksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.dst_port = m->udp.src_port;
        m->udp.src_port = htons(11211);
        m->udp.dgram_len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.dgram_cksum = 0;

        output { out(msglen, (void*) m, buff); }
            ''')

    class HandleArp(Element):
        def configure(self):
            self.inp = Input("void *", "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
    (void* pkt, void* buff) = inp();
    iokvs_message* msg = (iokvs_message*) pkt;
    struct arp_hdr *arp = (struct arp_hdr *) (&msg->ether + 1);
    int resp = 0;

    /* Currently we're only handling ARP here */
    if (msg->ether.ether_type == htons(ETHER_TYPE_ARP) &&
            arp->arp_hrd == htons(ARP_HRD_ETHER) && arp->arp_pln == 4 &&
            arp->arp_op == htons(ARP_OP_REQUEST) && arp->arp_hln == 6 &&
            arp->arp_data.arp_tip == settings.localip)
    {
        printf("Responding to ARP\n");
        resp = 1;
        struct ether_addr mymac = m->ether.d_addr;
        msg->ether.d_addr = msg->ether.s_addr;
        msg->ether.s_addr = mymac; // TODO
        arp->arp_op = htons(ARP_OP_REPLY);
        arp->arp_data.arp_tha = arp->arp_data.arp_sha;
        arp->arp_data.arp_sha = mymac;
        arp->arp_data.arp_tip = arp->arp_data.arp_sip;
        arp->arp_data.arp_sip = settings.localip;

        //rte_mbuf_refcnt_update(mbuf, 1);  // TODO

/*
        mbuf->ol_flags = PKT_TX_L4_NO_CKSUM;
        mbuf->tx_offload = 0;
/*
    }

    output switch { case resp: out(sizeof(struct ether_hdr) + sizeof(struct arp_hdr), pkt, buff); }
            ''')


    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;
uint8_t *val = m->payload + 4;
uint8_t opcode = m->mcr.request.opcode;
if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.opaque, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- id: %d, len: %d\n", m->mcr.request.opaque, m->mcr.request.bodylen);

output { out(msglen, (void*) m, buff); }
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
        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.null = Output()


        def states(self): self.this = main.item_allocators

        def impl(self):
            self.run_c(r'''
struct segment_header* segment = new_segment(this->ia[state.core], false);
if(segment == NULL) {
    printf("Fail to allocate new segment.\n");
    //exit(-1);
} else {
    state.segbase = get_pointer_offset(segment->data);
    state.seglen = segment->size;
}
ialloc_nicsegment_full(state.segfull);
output switch { case segment: out(); else: null(); }
            ''')  # TODO: maybe we should exit if segment = NULL?

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

    if(1) {  // TODO: change to 0 for performance
    int count = 1;
    segments_holder* p = this;
    while(p->next != NULL) {
        count++;
        p = p->next;
    }
    printf("addlog: new->segbase = %ld, cur->segbase = %ld\n", state.segbase, this->segbase);
    printf("logseg count = %d\n", count);
    }
            ''')

    ######################## item ########################

    class GetItem(Element):
        this = Persistent(segments_holder)

        def states(self):
            self.this = main.segments

        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    printf("item_alloc: segbase = %ld\n", this->segbase);
    item *it = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen);
    if(it == NULL && this->next) {
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

    state.segfull = full;

    if(it) {
        it->refcount = 1;

        printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n",
            state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, state.hash, totlen, it);
        it->hv = state.hash;
        it->vallen = totlen - state.pkt->mcr.request.keylen;
        it->keylen = state.pkt->mcr.request.keylen;
        memcpy(item_key(it), state.key, totlen);
        state.it = it;
    }

    output switch { case it: out();  else: nothing(); }
                ''')

        def impl_cavium(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    printf("item_alloc: segbase = %ld\n", this->segbase);
    void* addr = segment_item_alloc(this->segbase, this->seglen, &this->offset, sizeof(item) + totlen);
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

    state.segfull = full;

    if(addr) {
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
    }

    output switch { case addr: out();  else: nothing(); }
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

    class Drop(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c("")


    ########################## program #########################
    # def spec(self):
    #     class nic(InternalLoop):
    #         def impl(self):
    #             from_net = net_real.FromNet('from_net')
    #             classifier = main.Classifer()
    #             display = main.PrintMsg()
    #
    #             from_net.out >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> classifier
    #             from_net.nothing >> main.Drop()
    #             # get
    #             classifier.out_get >> main.HashGet() >> main.PrepareGetResp() >> main.Probe() >> display
    #             # set
    #             classifier.out_set >> main.GetItemSpec() >> main.HashPut() >> main.PrepareSetResp() >> main.Probe() \
    #             >> display
    #
    #     nic('nic', process='nic')

    def impl(self):
        MemoryRegion('data_region', 4 * 1024 * 512)

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 10000, n_cores, 3)
        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 10000, n_cores, 4, clean="enq")
        rx_enq = RxEnq()
        rx_deq = RxDeq()
        tx_enq = TxEnq()
        tx_deq = TxDeq()
        tx_scan = TxScan()

        ######################## NIC Rx #######################
        class nic_rx(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet('from_net')
                from_net_free = net_real.FromNetFree('from_net_free')
                to_net = net_real.ToNet('to_net')
                classifier = main.Classifer()
                check_packet = main.CheckPacket()

                # from_net
                from_net.nothing >> main.Drop()
                from_net.out >> check_packet
                check_packet.out >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> main.GetCore() >> classifier

                # get
                classifier.out_get >> rx_enq.inp[0]

                # set
                get_item = main.GetItem()
                classifier.out_set >> get_item
                get_item.out >> rx_enq.inp[1]
                # set (unseccessful)
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                get_item.nothing >> set_reponse_fail >> main.PrepareHeader() >> main.PrintMsg() >> to_net

                # full
                filter_full = main.FilterFull()
                get_item.out >> filter_full
                get_item.nothing >> filter_full
                filter_full >> rx_enq.inp[2]

                # exception
                check_packet.slowpath >> from_net_free  # TODO HandleArp
                check_packet.drop >> from_net_free


        ######################## APP #######################
        class process_eq(API):
            def configure(self):
                self.inp = Input(Size)

            def impl(self):
                self.inp >> rx_deq

                # get
                hash_get = main.HashGet()
                rx_deq.out[0] >> hash_get
                hash_get.out >> tx_enq.inp[0]
                hash_get.null >> tx_enq.inp[3]

                # set
                rx_deq.out[1] >> main.HashPut() >> main.Unref() >> tx_enq.inp[1]

                # full
                new_segment = main.NewSegment()
                rx_deq.out[2] >> new_segment
                new_segment.out >> tx_enq.inp[2]
                new_segment.null >> main.Drop()


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
                tx_scan.out[3] >> clean
                clean >> self.out

        ####################### NIC Tx #######################
        class nic_tx(InternalLoop):
            def impl(self):
                to_net = net_real.ToNet('to_net')
                prepare_header = main.PrepareHeader()
                display = main.PrintMsg()
                main.Scheduler() >> tx_deq

                # get
                tx_deq.out[0] >> main.PrepareGetResp() >> prepare_header
                tx_deq.out[3] >> main.PrepareGetNullResp() >> prepare_header

                # set
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                tx_deq.out[1] >> set_response >> prepare_header
                prepare_header >> display >> to_net

                # full
                tx_deq.out[2] >> main.AddLogseg()

        nic_rx('nic_rx', process='dpdk', cores=[1])
        process_eq('process_eq', process='app')
        init_segment('init_segment', process='app')
        clean_cq('clean_cq', process='app')
        nic_tx('nic_tx', process='dpdk', cores=[2])

master_process('app')

# NIC: ['jenkins_hash', 'ialloc', 'settings']
# APP: ['jenkins_hash', 'hashtable', 'ialloc', 'settings']


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = {"test_app": ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'app'],
            "test_nic": ['jenkins_hash', 'ialloc', 'settings', 'dpdk']}
c.compile_and_run(["test_app", "test_nic"])


# TODO: spec
