from dsl2 import *
import queue_smart2, net_real
from compiler import Compiler
import library_dsl2

n_cores = 4
nic_rx_threads = 2
nic_tx_threads = 3

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
    ether = Field('struct ether_hdr')
    ipv4 = Field('struct ipv4_hdr')
    dup = Field('struct udp_hdr')
    mcudp = Field('memcached_udp_header')
    mcr = Field(protocol_binary_request_header)
    payload = Field(Array(Uint(8)))

    def init(self): self.declare = False

class item(State):
    next = Field('struct _item')
    hv = Field(Uint(32))
    vallen = Field(Uint(32))
    refcount = Field(Uint(16))
    keylen = Field(Uint(16))
    flags = Field(Uint(32))

    def init(self): self.declare = False

class MyState(State):
    pkt = Field(Pointer(iokvs_message))
    pkt_buff = Field('void*')
    it = Field(Pointer(item), shared='data_region')
    key = Field('void*', copysize='state.pkt->mcr.request.keylen')
    hash = Field(Uint(32))
    segfull = Field(Uint(64))
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    core = Field(Uint(16))
    vallen = Field(Uint(32))
    src_mac = Field('struct ether_addr')
    dst_mac = Field('struct ether_addr')
    src_ip = Field(Uint(32))
    src_port = Field(Uint(16))

class Schedule(State):
    core = Field(Size)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field(Array('struct item_allocator*', n_cores))

class segment(State):
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    offset = Field(Uint(64))

class segment_holders(State):
    segments = Field(Array(segment, 16))
    head = Field(Int)
    tail = Field(Int)
    len = Field(Int)
    lock = Field('lock_t')

    def init(self):
        self.len = 16
        self.lock = lambda x: 'qlock_init(&%s)' % x

class main(Pipeline):
    state = PerPacket(MyState)

    class SaveState(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")
            self.out = Output()

        def impl(self):
            self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;
state.pkt = m;
state.pkt_buff = buff;
state.src_mac = m->ether.s_addr;
state.dst_mac = m->ether.d_addr;
state.src_ip = m->ipv4.src_addr;
state.src_port = m->udp.src_port;

output { out(); }
            ''')

    class GetPktBuff(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output("void*", "void*")

        def impl(self):
            self.run_c(r'''
    void* pkt = state.pkt;
    void* pkt_buff = state.pkt_buff;
    output { out(pkt, pkt_buff); }
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
    uint32_t blen = m->mcr.request.bodylen;
    uint32_t keylen = m->mcr.request.keylen;

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
uint8_t cmd = state.pkt->mcr.request.opcode;
//printf("receive: %d\n", cmd);

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
output { out(); }''')

    class GetCore(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
int core = state.hash %s %d;;
state.core = core;
//printf("hash = %s, core = %s\n", state.hash, core);
            output { out(); }''' % ('%', n_cores, '%d', '%d'))

    ######################## hash ########################

    class JenkinsHash(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.hash = jenkins_hash(state.key, state.pkt->mcr.request.keylen);
output { out(); }
            ''')

    class HashGet(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.null = Output()

        def impl(self):
            self.run_c(r'''
item* it = hasht_get(state.key, state.pkt->mcr.request.keylen, state.hash);
//printf("hash get\n");
state.it = it;
output switch { case it: out(); else: null(); }
            ''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
//printf("hash put\n");
hasht_put(state.it, NULL);
output { out(); }
            ''')


    ######################## responses ########################

    class Scheduler(Element):
        this = Persistent(Schedule)

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(Size)
            self.log = Output(Size)
            self.this = Schedule()

        def impl(self):
            self.run_c(r'''
size_t core_id = inp();
size_t n_cores = %d;
size_t mod = %d;

static __thread int core = -1;
if(core == -1) core = (core_id * mod)/%d;

core = (core + 1) %s mod;
output switch {
  case(core < n_cores): out(core);
  else: log(0);
  }''' % (n_cores, n_cores+1, nic_tx_threads, '%'))

    class SizeGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
//printf("size get\n");
    size_t msglen = sizeof(iokvs_message) + 4 + state.it->vallen;
    state.vallen = state.it->vallen;
    output { out(msglen); }
            ''')

        def impl_cavium(self):
            self.run_c(r'''
    uint32_t* vallen
    dma_read(&state.it->vallen, sizeof(uint32_t), (void**) &vallen);
    size_t msglen = sizeof(iokvs_message) + 4 + *vallen;
    state.vallen = *vallen;
    dma_free(vallen);
    output { out(msglen); }
                        ''')

    class PrepareGetResp(Element):
        def configure(self):
            self.inp = Input(Size, 'void*', 'void*')
            self.out = Output(Size, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
        (size_t msglen, void* pkt, void* pkt_buff) = inp();

        iokvs_message *m = pkt;
        memcpy(m, &iokvs_template, sizeof(iokvs_message));
        item* it = state.it;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_SUCCESS;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state.vallen;
rte_memcpy(m->payload + 4, item_value(it), state.vallen);

output { out(msglen, m, pkt_buff); }
            ''')

        def impl_cavium(self):
            self.run_c(r'''
        (size_t msglen, void* pkt, void* pkt_buff) = inp();
        iokvs_message *m = pkt;
        memcpy(m, &iokvs_template, sizeof(iokvs_message));
        item* it = state.it;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_SUCCESS;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state.vallen;

void* value;
dma_read(item_value(it), state.vallen, (void**) &value);
rte_memcpy(m->payload + 4, value, state.vallen);
dma_free(value);

output { out(msglen, m, pkt_buff); }
            ''')

    class SizeGetNullResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
//printf("size get null\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }
            ''')

    class PrepareGetNullResp(Element):
        def configure(self):
            self.inp = Input(Size, 'void*', 'void*')
            self.out = Output(Size, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
            (size_t msglen, void* pkt, void* pkt_buff) = inp();
            iokvs_message *m = pkt;
            memcpy(m, &iokvs_template, sizeof(iokvs_message));

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_KEY_ENOENT;

    m->mcr.request.keylen = 0;
    m->mcr.request.extlen = 4;
    m->mcr.request.bodylen = 4;
    *((uint32_t *)m->payload) = 0;

    output { out(msglen, m, pkt_buff); }
                ''')

    class SizeSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
//printf("size set\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }
            ''')

    class SizePktBuffSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''
            size_t msglen = sizeof(iokvs_message) + 4;
            void* pkt = state.pkt;
            void* pkt_buff = state.pkt_buff;
            output { out(msglen, pkt, pkt_buff); }
            ''')

    class PrepareSetResp(Element):
        def configure(self, status):
            self.inp = Input(Size, 'void*', 'void*')
            self.out = Output(Size, Pointer(iokvs_message), 'void*')
            self.status = status
            # PROTOCOL_BINARY_RESPONSE_SUCCESS
            # PROTOCOL_BINARY_RESPONSE_ENOMEM

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* pkt_buff) = inp();
iokvs_message *m = pkt;
memcpy(m, &iokvs_template, sizeof(iokvs_message));

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = %s;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(msglen, m, pkt_buff); }
            ''' % self.status)


    class PrepareHeader(Element):
        def configure(self):
            self.inp = Input(Size, Pointer(iokvs_message), "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
        (size_t msglen, iokvs_message* m, void* buff) = inp();
            
        m->ether.d_addr = state.src_mac;
        m->ether.s_addr = state.dst_mac; //settings.localmac;
        m->ipv4.dst_addr = state.src_ip;
        m->ipv4.src_addr = settings.localip;
        m->ipv4.total_length = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4.time_to_live = 64;
        m->ipv4.hdr_checksum = 0;
        //m->ipv4.hdr_checksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.dst_port = state.src_port;
        m->udp.src_port = htons(11211);
        m->udp.dgram_len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.dgram_cksum = 0;

        output { out(msglen, (void*) m, buff); }
            ''')

    class HandleArp(Element):
        def configure(self):
            self.inp = Input("void *", "void *")
            self.out = Output(Size, "void *", "void *")
            self.drop = Output("void *", "void *")

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
        struct ether_addr mymac = msg->ether.d_addr;
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
*/
    }

    output switch { 
      case resp: out(sizeof(struct ether_hdr) + sizeof(struct arp_hdr), pkt, buff); 
            else: drop(pkt, buff);
    }
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

/*
static count = 0;
count++;
if(count == 10000) {
count = 0;
if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- status: %d, len: %d, val:%d\n", m->mcr.request.status, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- status: %d, len: %d\n", m->mcr.request.status, m->mcr.request.bodylen);
}
*/
output { out(msglen, (void*) m, buff); }
    ''')


    ######################## log segment #######################

    item_allocators = ItemAllocators()

    class FilterFull(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state.core = 0;
output switch { case state.segfull: out(); }''')


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
struct segment_header *h = ialloc_nicsegment_alloc(ia);
//state.core = core;
state.core = 0;
state.segbase = get_pointer_offset(h->data);
state.seglen = h->size;
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
uint32_t core_id = ialloc_nicsegment_full(state.segfull);
struct segment_header* segment = ialloc_nicsegment_alloc(this->ia[core_id]);
if(segment == NULL) {
    printf("Fail to allocate new segment.\n");
    //exit(-1);
} else {
    state.segbase = get_pointer_offset(segment->data);
    state.seglen = segment->size;
    state.core = 0;
    //printf("New segment: segbase = %p.\n", (void*) get_pointer_offset(segment->data));

}
output switch { case segment: out(); else: null(); }
            ''')  # TODO: maybe we should exit if segment = NULL?

    segments = segment_holders()

    class AddLogseg(Element):
        this = Persistent(segment_holders)

        def configure(self):
            self.inp = Input()
            self.this = main.segments

        def impl(self):
            self.run_c(r'''
        qlock_lock(&this->lock);
        segment* h = &this->segments[this->tail];
        h->segbase = state.segbase;
        h->seglen = state.seglen;
        h->offset = 0;
        __sync_synchronize();
        this->tail = (this->tail + 1) % this->len;

        if(this->head == this->tail) {
            printf("NIC segment holder is full.\n");
            abort();
        }

            printf("addlog: new->segaddr = %p, cur->segaddr = %p\n", (void*) h->segbase, (void*) this->segments[this->head].segbase);
        printf("holder: head = %d, tail = %d\n", this->head, this->tail);
        qlock_unlock(&this->lock);
            ''')

    ######################## item ########################

    class GetItem(Element):
        this = Persistent(segment_holders)

        def states(self):
            self.this = main.segments

        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''
    static __thread segment* h = NULL;
    while(h == NULL && this->head != this->tail) {
        uint32_t old = this->head;
        uint32_t new = (old + 1) % this->len;
        if(__sync_bool_compare_and_swap(&this->head, old, new)) {
            h = &this->segments[old];
            printf("h = %p\n", h);
            break;
        }
    }

    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    item *it = NULL;
    if(h) {
        it = segment_item_alloc(h->segbase, h->seglen, &h->offset, sizeof(item) + totlen);

        if(it == NULL) {
            printf("Segment is full. offset = %dd\n", h->offset);  // including this line will make CPU keep making new segment. Without this line, # of segment will stop under 100.
            full = (uintptr_t) h->segbase + h->offset;
            // when tx queue is backed up, CPU will have high number of segment, but NIC will never get anything back.
            h = NULL;

            while(h == NULL && this->head != this->tail) {
                int old = this->head;
                int new = (old + 1) % this->len;
                if(__sync_bool_compare_and_swap(&this->head, old, new)) {
                    h = &this->segments[old];
                    break;
                }
            }

            if(h) {
                it = segment_item_alloc(h->segbase, h->seglen, &h->offset, sizeof(item) + totlen);
            }
        }
    }

    //printf("it = %p, full = %p\n", it, (void*) full);
    state.segfull = full;

    if(it) {
        it->refcount = 1;
        uint16_t keylen = state.pkt->mcr.request.keylen;

        //    printf("get_item id: %d, keylen: %ld, totlen: %ld, item: %ld\n",
        //state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, totlen, it);
        it->hv = state.hash;
        it->vallen = totlen - keylen;
        it->keylen = keylen;
        memcpy(item_key(it), state.key, totlen);
        state.it = it;
    }

    output switch { case it: out();  else: nothing(); }

                ''')

    class GetItemSpec(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    item *it = (item *) malloc(sizeof(item) + totlen);

    //printf("get_item id: %d, keylen: %ld, totlen: %ld, item: %ld\n",
    //         state.pkt->mcr.request.opaque, state.pkt->mcr.request.keylen, totlen, it);
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
        if(state.it) item_unref(state.it);
        output { out(); }
            ''')

    class Clean(Element):
        def configure(self, val):
            self.inp = Input()
            self.out = Output(Bool)
            self.val = val

        def impl(self):
            self.run_c(r'''output { out(%s); }''' % self.val)

    class Drop(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c("")

    class ForwardBool(Element):
        def configure(self):
            self.inp = Input(Bool)
            self.out = Output(Bool)

        def impl(self):
            self.run_c(r'''
            (bool x) = inp();
            output { out(x); }
            ''')


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
        MemoryRegion('data_region', 2 * 1024 * 1024 * 512) #4 * 1024 * 512)

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 32*1024, n_cores, 2,
                                                        enq_output=True, enq_blocking=True, enq_atomic=True)
        # ^ if enq_blocking = false, need to call item_unref if queue is full on set_request.
        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 32*1024, n_cores, 3, clean="enq",
                                                        enq_blocking=True, deq_atomic=True)  # debug: size = 1 KB, real: size = 64 KB
        rx_enq = RxEnq()
        rx_deq = RxDeq()
        tx_enq = TxEnq()
        tx_deq = TxDeq()
        tx_scan = TxScan()

        LogInEnq, LogInDeq, LogInScan = queue_smart2.smart_queue("log_in_queue", 1024, 1, 1,
                                                                 enq_blocking=True, enq_atomic=True)
        LogOutEnq, LogOutDeq, LogOutScan = queue_smart2.smart_queue("log_out_queue", 1024, 1, 1,
                                                                    enq_blocking=True, deq_atomic=True)
        log_in_enq = LogInEnq()
        log_in_deq = LogInDeq()
        log_out_enq = LogOutEnq()
        log_out_deq = LogOutDeq()

        ######################## NIC Rx #######################
        class nic_rx(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet('from_net')
                from_net_free = net_real.FromNetFree('from_net_free')
                to_net = net_real.ToNet('to_net', configure=['from_net'])
                classifier = main.Classifer()
                check_packet = main.CheckPacket()
                hton1 = net_real.HTON(configure=['iokvs_message'])
                hton2 = net_real.HTON(configure=['iokvs_message'])

                # from_net
                from_net.nothing >> main.Drop()
                from_net.out >> hton1 >> check_packet
                check_packet.out >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> main.GetCore() >> classifier

                # get
                classifier.out_get >> rx_enq.inp[0]

                # set
                get_item = main.GetItem()
                classifier.out_set >> get_item >> rx_enq.inp[1]
                # set (unseccessful)
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                get_item.nothing >> main.SizePktBuffSetResp() >> set_reponse_fail >> main.PrepareHeader() \
                >> main.PrintMsg() >> hton2 >> to_net

                # full
                filter_full = main.FilterFull()  # TODO: impose order of state.core assignment: how to make sure that FilterFull doesn't run before rx_enq
                get_item.out >> filter_full
                get_item.nothing >> filter_full
                filter_full >> log_in_enq.inp[0]

                # exception
                arp = main.HandleArp()
                check_packet.slowpath >> arp >> to_net

                # free from_net
                arp.drop >> from_net_free
                check_packet.drop >> from_net_free
                rx_enq.done >> main.GetPktBuff() >> from_net_free


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
                hash_get.null >> tx_enq.inp[2]
                # set
                rx_deq.out[1] >> main.HashPut() >> main.Unref() >> tx_enq.inp[1]

                # cleaning tx queue
                drop = main.Drop()
                tx_scan.out[0] >> main.Unref() >> drop

                tx_scan.out[1] >> drop
                tx_scan.out[2] >> drop

        class init_segment(API):
            def configure(self):
                self.inp = Input(Size)

            def impl(self):
                self.inp >> main.FirstSegment() >> log_out_enq.inp[0]

        class create_segment(API):
            def impl(self):
                new_segment = main.NewSegment()
                library_dsl2.Constant(configure=[0]) >> log_in_deq
                log_in_deq.out[0] >> new_segment >> log_out_enq.inp[0]
                new_segment.null >> main.Drop()

        ####################### NIC Tx #######################
        class nic_tx(InternalLoop):
            def impl(self):
                scheduler = main.Scheduler()
                to_net = net_real.ToNet('to_net', configure=['alloc'])
                net_alloc0 = net_real.NetAlloc('net_alloc0')
                net_alloc1 = net_real.NetAlloc('net_alloc1')
                net_alloc3 = net_real.NetAlloc('net_alloc3')
                prepare_header = main.PrepareHeader()
                display = main.PrintMsg()
                hton = net_real.HTON(configure=['iokvs_message'])
                drop = main.Drop()

                self.core_id >> scheduler >> tx_deq
                scheduler.log >> log_out_deq

                # get
                tx_deq.out[0] >> main.SizeGetResp() >> net_alloc0 >> main.PrepareGetResp() >> prepare_header
                tx_deq.out[2] >> main.SizeGetNullResp() >> net_alloc3 >> main.PrepareGetNullResp() >> prepare_header

                # set
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                tx_deq.out[1] >> main.SizeSetResp() >> net_alloc1 >> set_response >> prepare_header

                # send
                prepare_header >> display >> hton >> to_net


                # free net_alloc
                net_alloc0.oom >> drop
                net_alloc1.oom >> drop
                net_alloc3.oom >> drop

                # full
                log_out_deq.out[0] >> main.AddLogseg()

        nic_rx('nic_rx', process='dpdk', cores=[nic_tx_threads + i for i in range(nic_rx_threads)])
        process_eq('process_eq', process='app')
        init_segment('init_segment', process='app')
        create_segment('create_segment', process='app')
        nic_tx('nic_tx', process='dpdk', cores=range(nic_tx_threads))

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
            "test_nic": ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'dpdk']}
c.compile_and_run(["test_app", "test_nic"])


# TODO: spec
