from dsl2 import *
import queue_smart2, net_real, library_dsl2
from compiler import Compiler

n_cores = 7
nic_rx_threads = 5
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
    ether = Field('struct ehter_hdr')
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
    it = Field(Pointer(item))
    it_addr = Field(Uint(64))
    key = Field('void*', copysize='state.pkt->mcr.request.keylen')
    hash = Field(Uint(32))
    segfull = Field(Uint(64))
    segbase = Field(Uint(64))
    segaddr = Field(Uint(64))
    seglen = Field(Uint(64))
    core = Field(Uint(16))
    vallen = Field(Uint(32))
    keylen = Field(Uint(16))
    src_mac = Field('struct eth_addr')
    dst_mac = Field('struct eth_addr')
    src_ip = Field('struct ip_addr')
    src_port = Field(Uint(16))
    resp_size = Field(Size)
    resp = Field(Pointer(iokvs_message), copysize='state.resp_size')  # TODO: make sure vallen is set

class Schedule(State):
    core = Field(Size)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field(Array('struct item_allocator*', n_cores))

class segment(State):
    segbase = Field(Uint(64))
    segaddr = Field(Uint(64))
    seglen = Field(Uint(64))
    offset = Field(Uint(64))

class segment_holders(State):
    segments = Field(Array(segment, 16))
    head = Field(Uint(32))
    tail = Field(Uint(32))
    len = Field(Uint(32))
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
state.src_mac = m->ether.src;
state.dst_mac = m->ether.dest;
state.src_ip = m->ipv4.src;
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

if (m->ether.type == htons(ETHERTYPE_IPv4) &&
    m->ipv4._proto == 17 &&
    memcmp(m->ipv4.dest.addr, settings.localip.addr, sizeof(struct ip_addr)) == 0 &&
    //m->ipv4.dest == settings.localip &&
    m->udp.dest_port == htons(11211) &&
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
//printf("classify: %d\n", cmd);

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
#ifdef DEBUG
printf("hash = %s, keylen = %s, core = %s\n", state.pkt->mcr.request.keylen, state.hash, core);
#endif
            output { out(); }''' % ('%', n_cores, '%d', '%d', '%d'))

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
#ifdef DEBUG
            printf("hash get: keylen = %d, hash = %d\n", state.pkt->mcr.request.keylen, state.hash);
#endif
state.it = it;
if(it) state.it_addr = it->addr;
output switch { case it: out(); else: null(); }
            ''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
#ifdef DEBUG
printf("hash put: state.it = %p\n", state.it);
#endif
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
      case((size_t) core < n_cores): out(core);
      else: log(0);
      }''' % (n_cores, n_cores + 1, nic_tx_threads, '%'))


    class Malloc(Element):
        def configure(self):
            self.inp = Input(Size)
            self.out = Output(Size, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''
    size_t size = inp();
    void* p = malloc(size);
    output { out(size, p, NULL); }
            ''')


    class SizeGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
    size_t msglen = sizeof(iokvs_message) + 4 + state.it->vallen;
            //printf("size get: vallen = %d, size = %ld\n", state.it->vallen, msglen);
    state.resp_size = msglen;
    state.vallen = state.it->vallen;
    state.keylen = state.it->keylen;
    state.it_addr;  // to make state.addr live.
    output { out(msglen); }
            ''')

        def impl_cavium(self):
            self.run_c(r'''
    item* it;
    dma_read(state.it_addr, sizeof(item), (void**) &it);
    state.keylen = nic_htons(it->keylen);
    state.vallen = nic_htonl(it->vallen);
    dma_free(it);
    size_t msglen = sizeof(iokvs_message) + 4 + state.vallen;

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
        memcpy(m, iokvs_template(), sizeof(iokvs_message));
        item* it = state.it;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_SUCCESS);

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = htonl(4);
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state.vallen;
rte_memcpy(m->payload + 4, item_value(it), state.vallen);

output { out(msglen, m, pkt_buff); }
            ''')

        def impl_cavium(self):
            self.run_c(r'''
        (size_t msglen, void* pkt, void* pkt_buff) = inp();
        iokvs_message *m = pkt;
        memcpy(m, iokvs_template(), sizeof(iokvs_message));

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_SUCCESS;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state.vallen;

uint8_t* value;
dma_read(state.it_addr + sizeof(item) + state.keylen, state.vallen, (void**) &value);
memcpy(m->payload + 4, value, state.vallen);
dma_free(value);

output { out(msglen, m, pkt_buff); }
            ''')  # TODO: hton conversion???

    class SizeGetNullResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
    size_t msglen = sizeof(iokvs_message) + 4;
            //printf("size get null: size = %ld\n", msglen);
    state.resp_size = msglen;
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
            memcpy(m, iokvs_template(), sizeof(iokvs_message));

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_KEY_ENOENT);

    m->mcr.request.keylen = 0;
    m->mcr.request.extlen = 4;
    m->mcr.request.bodylen = htonl(4);
    *((uint32_t *)m->payload) = 0;

    output { out(msglen, m, pkt_buff); }
                ''')

    class SizeSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
    size_t msglen = sizeof(iokvs_message) + 4;
            //printf("size set: size = %ld\n", msglen);
    state.resp_size = msglen;
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
memcpy(m, iokvs_template(), sizeof(iokvs_message));

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = htons(%s);

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

        m->ether.dest = state.src_mac;
        m->ether.src = state.dst_mac; //settings.localmac;
        m->ipv4.dest = state.src_ip;
        m->ipv4.src = settings.localip;
        m->ipv4._len = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4._ttl = 64;
        m->ipv4._chksum = 0;
        //m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.dest_port = htons(state.src_port);
        m->udp.src_port = htons(11211);
        m->udp.len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.cksum = 0;

        output { out(msglen, (void*) m, buff); }
            ''')

    class SaveResponse(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    (size_t msglen, void* m, void* buff) = inp();
    state.resp = m;
    output { out(); }
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
    if (msg->ether.type == htons(ETHERTYPE_ARP) &&
            arp->arp_hrd == htons(ARPHRD_ETHER) && arp->arp_pln == 4 &&
            arp->arp_op == htons(ARPOP_REQUEST) && arp->arp_hln == 6 &&
            memcmp(arp->arp_tip.addr, settings.localip.addr, sizeof(struct ip_addr)) == 0
            //arp->arp_tip == settings.localip
            )
    {
        printf("Responding to ARP\n");
        resp = 1;
        struct eth_addr mymac = msg->ether.dest;
        msg->ether.dest = msg->ether.src;
        msg->ether.src = mymac; // TODO

        arp->arp_op = htons(ARPOP_REPLY);
        arp->arp_tha = arp->arp_sha;
        arp->arp_sha = mymac;
        arp->arp_tip = arp->arp_sip;
        arp->arp_sip = settings.localip;

        //rte_mbuf_refcnt_update(mbuf, 1);  // TODO

/*
        mbuf->ol_flags = PKT_TX_L4_NO_CKSUM;
        mbuf->tx_offload = 0;
*/
    }

    output switch { 
      case resp: out(sizeof(struct eth_hdr) + sizeof(struct arp_hdr), pkt, buff); 
            else: drop(pkt, buff);
    }
            ''')

    class ExtractPkt(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
iokvs_message* resp = state.resp;
size_t msglen = state.resp_size; //sizeof(iokvs_message) + resp->mcr.request.bodylen;

output { out(msglen, (void*) resp, NULL); }
            ''')  # TODO: dpdk supports buf = NULL; if buf == NULL: create buffer and copy


    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;

#ifdef DEBUG
uint8_t *val = m->payload + 4;
uint8_t opcode = m->mcr.request.opcode;

if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- status: %d, val:%d, len: %d\n", m->mcr.request.status, val[0], m->mcr.request.bodylen);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- status: %d, len: %d\n", m->mcr.request.status, m->mcr.request.bodylen);
#endif

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
state.segbase = (uint64_t) h->data;
state.segaddr = h->addr;
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
    state.segbase = segment->data;
    state.segaddr = segment->addr;
    state.seglen = segment->size;
    state.core = 0;
}
output switch { case segment: out(); else: null(); }
            ''')

    segments = segment_holders()

    class AddLogseg(Element):  # TODO: concurency version
        this = Persistent(segment_holders)

        def configure(self):
            self.inp = Input()
            self.this = main.segments

        def impl(self):
            self.run_c(r'''
        spinlock_lock(&this->lock);
        segment* h = &this->segments[this->tail];
        h->segbase = state.segbase;
        h->segaddr = state.segaddr;
        h->seglen = state.seglen;
        h->offset = 0;
        //__sync_synchronize(); // CVMX_SYNCWS for cavium
        __SYNC;
        this->tail = (this->tail + 1) % this->len;

        if(this->head == this->tail) {
            printf("NIC segment holder is full.\n");
            abort();
        }

        printf("addlog: new->segaddr = %p, cur->segaddr = %p\n", (void*) h->segaddr, (void*) this->segments[this->head].segaddr);
        printf("holder: head = %d, tail = %d\n", this->head, this->tail);
        spinlock_unlock(&this->lock);

            ''')

    ######################## item ########################

    class GetItem(Element):  # TODO: concurency version
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
            break;
        }
    }

    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    item *it = NULL;
    if(h) {
        it = segment_item_alloc(h->segaddr, h->seglen, &h->offset, sizeof(item) + totlen);

        if(it == NULL) {
            printf("Segment is full. offset = %dd\n", h->offset);  // including this line will make CPU keep making new segment. Without this line, # of segment will stop under 100.
            full = h->segaddr + h->offset;
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
                it = segment_item_alloc(h->segaddr, h->seglen, &h->offset, sizeof(item) + totlen);
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

        def impl_cavium(self):  # TODO: concurrent version -- each thread maintain current segment.
            self.run_c(r'''
    static __thread segment* h = NULL;
    while(h == NULL && this->head != this->tail) {
        int old = this->head;
        int new = (old + 1) % this->len;
        if(cvmx_atomic_compare_and_store32(&this->head, old, new)) {
            h = &this->segments[old];
            printf("h = %p\n", h);
            break;
        }
    }

    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;

    uint64_t full = 0;
    uint64_t addr = 0;

    if(h) {
        addr = segment_item_alloc(h->segaddr, h->seglen, &h->offset, sizeof(item) + totlen);  // TODO: concurrent

        if(addr == 0) {
            printf("Segment is full. offset = %ld\n", h->offset);  // including this line will make CPU keep making new segment. Without this line, # of segment will stop under 100.
            full = h->segaddr + h->offset;
            // when tx queue is backed up, CPU will have high number of segment, but NIC will never get anything back.
            h = NULL;

            while(this->head != this->tail) {
                int old = this->head;
                int new = (old + 1) % this->len;
                if(cvmx_atomic_compare_and_store32(&this->head, old, new)) {
                    h = &this->segments[old];
                    break;
                }
            }

            if(h) {
                addr = segment_item_alloc(h->segaddr, h->seglen, &h->offset, sizeof(item) + totlen);
            }
        }
    }

    state.segfull = full;

    if(addr) {
        item *it;
        dma_buf_alloc((void**) &it);
        //dma_read(addr, sizeof(item), (void**) &it);
        it->refcount = nic_ntohs(1);

        //printf("get_item keylen: %d, totlen: %ld, item: %p\n",
        //    state.pkt->mcr.request.keylen, totlen, (void*) it);
        it->hv = nic_ntohl(state.hash);
        it->vallen = nic_ntohl(totlen - state.pkt->mcr.request.keylen);
        it->keylen = nic_ntohs(state.pkt->mcr.request.keylen);
        it->addr = nic_ntohp(addr);
        memcpy(item_key(it), state.key, totlen);
        dma_write(addr, sizeof(item) + totlen, it, 1);
        dma_free(it);
        state.it = (item*) (addr - h->segaddr + h->segbase);
    }

    output switch { case addr: out();  else: nothing(); }
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
        if(state.it) { 
          item_unref(state.it);
          state.it = NULL;
        }
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

    class Free(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c("free(state.resp);")

    class ForwardBool(Element):
        def configure(self):
            self.inp = Input(Bool)
            self.out = Output(Bool)

        def impl(self):
            self.run_c(r'''
            (bool x) = inp();
            output { out(x); }
            ''')

    ########################### Fake net elements ###############################
    class FromNet(Element):
        def configure(self):
            self.out = Output(Size, "void *", "void *")  # packet, buffer
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''
        static uint8_t v = 0;
        iokvs_message* m = NULL;
        if(v < 100) {
            printf("\n");
            m = random_request(v);
            v++;
        }

        output switch {
            case m != NULL: out(sizeof(iokvs_message) + m->mcr.request.bodylen, m, NULL);
            case m == NULL: nothing();
        }
            ''')

    class FromNetFree(Element):
        def configure(self):
            self.inp = Input("void *", "void *")  # packet, buffer

        def impl(self):
            self.run_c(r'''
        (void* p, void* buf) = inp();
        free(p);
            ''')

    class ToNet(Element):
        def configure(self):
            self.inp = Input(Size, "void *", "void *")  # size, packet, buffer

        def impl(self):
            self.run_c(r'''
        (size_t len, void* p, void* buf) = inp();
        free(p);
            ''')

    class NetAlloc(Element):
        def configure(self):
            self.inp = Input(Size)
            self.out = Output(Size, "void *", "void *")  # packet, buffer
            self.oom = Output()

        def impl(self):
            self.run_c(r'''
        (size_t len) = inp();
        void *data = malloc(len);
        output switch {
            case data != NULL: out(len, data, NULL);
            else: oom();
        }
            ''')

    def impl(self):

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 512 * 64, n_cores, 2, overlap=64, #64
                                                        enq_output=True, enq_blocking=True, enq_atomic=True)  # enq_blocking=False?
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 512 * 160, n_cores, 1, overlap=160, #160
                                                        checksum=True,
                                                        enq_blocking=True, enq_output=True, deq_atomic=True)
        tx_enq = TxEnq()
        tx_deq = TxDeq()

        LogInEnq, LogInDeq, LogInScan = queue_smart2.smart_queue("log_in_queue", 8 * 1024, 1, 1, overlap=32,
                                                                 enq_blocking=True, enq_atomic=True)
        LogOutEnq, LogOutDeq, LogOutScan = queue_smart2.smart_queue("log_out_queue", 8 * 1024, 1, 1, overlap=32,
                                                                    checksum=False,
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

                #from_net = main.FromNet()
                #from_net_free = main.FromNetFree()
                #to_net = main.ToNet()

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
                filter_full = main.FilterFull()
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
                prepare_header = main.PrepareHeader()

                self.inp >> rx_deq

                # get
                hash_get = main.HashGet()
                rx_deq.out[0] >> hash_get
                hash_get.out >> main.SizeGetResp() >> main.Malloc() >> main.PrepareGetResp() >> prepare_header
                hash_get.null >> main.SizeGetNullResp() >> main.Malloc() >> main.PrepareGetNullResp() >> prepare_header

                # set
                rx_deq.out[1] >> main.HashPut() >> main.SizeSetResp() >> main.Malloc() \
                >> main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS']) >> prepare_header

                prepare_header >> main.SaveResponse() >> tx_enq.inp[0]
                tx_enq.done >> main.Unref() >> main.Free()


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
                to_net = net_real.ToNet('to_net', configure=['from_net'])
                display = main.PrintMsg()
                hton = net_real.HTON(configure=['iokvs_message'])
                extract_pkt = main.ExtractPkt()

                self.core_id >> scheduler >> tx_deq
                tx_deq.out[0] >> extract_pkt >> display >> hton >> to_net

                # log
                scheduler.log >> log_out_deq
                log_out_deq.out[0] >> main.AddLogseg()

        nic_rx('nic_rx', device=target.CAVIUM, cores=[nic_tx_threads + i for i in range(nic_rx_threads)])
        process_eq('process_eq', process='app')
        init_segment('init_segment', process='app')
        create_segment('create_segment', process='app')
        nic_tx('nic_tx', device=target.CAVIUM, cores=range(nic_tx_threads))

master_process('app')


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.init = r'''
  settings_init(argv);  // TODO: settings_init must be called before other inits.
  //ialloc_init();
  '''
c.generate_code_as_header()
c.depend = {"test_app": ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'app']}
c.compile_and_run(["test_app"])
