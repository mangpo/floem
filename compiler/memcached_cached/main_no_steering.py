from dsl2 import *
from compiler import Compiler
import net_real, library_dsl2, queue_smart2

n_cores = 9
miss_every = 10

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
    ether = Field('struct eth_hdr')
    ipv4 = Field('struct ip_hdr')
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
    pkt = Field(Pointer(iokvs_message), copysize='state.pkt_size')
    pkt_buff = Field('void*')
    pkt_size = Field(Size)
    it = Field(Pointer(item), shared='data_region')
    hash = Field(Uint(32))
    core = Field(Uint(16))
    vallen = Field(Uint(32))

    resp_size = Field(Size)
    resp = Field(Pointer(iokvs_message), copysize='state.resp_size')  # TODO: make sure vallen is set

class Schedule(State):
    core = Field(Size)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field('struct item_allocator*')

    def init(self):
        self.ia = 'get_item_allocators()'

item_allocators = ItemAllocators()
item_allocators_cpu = ItemAllocators()

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
    iokvs_message* m = (iokvs_message*) pkt;
    state.pkt = m;
    state.pkt_size = size;
    state.pkt_buff = buff;
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

state.pkt = NULL;
state.core = cvmx_get_core_num();
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

    class CacheSimulator(Element):
        def configure(self):
            self.inp = Input()
            self.out_hit = Output()
            self.out_miss = Output()

        def impl(self):
            self.run_c(r'''
    static int round = 0;
    bool hit = true;
    round++;
    if(round == %d) {
        round = 0;
        hit = false;
    }

    output switch {
        case hit: out_hit();
        else: out_miss();
    }
            ''' % miss_every)

    class Classifer(Element):
        def configure(self):
            self.inp = Input()
            self.out_get = Output()
            self.out_set = Output()

        def impl(self):
            self.run_c(r'''
iokvs_message* pkt = state.pkt;
uint8_t cmd = pkt->mcr.request.opcode;
//printf("receive: %d\n", cmd);

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get();
  else: out_set();
  // else drop
}
            ''')

    ######################## hash ########################

    class JenkinsHash(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
void* key = state.pkt->payload + state.pkt->mcr.request.extlen;
uint32_t hash = jenkins_hash(key, state.pkt->mcr.request.keylen);
state.hash = hash;
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
        iokvs_message* pkt = state.pkt;
        void* key = pkt->payload + pkt->mcr.request.extlen;
        item* it = hasht_get(key, htons(pkt->mcr.request.keylen), state.hash);
        //printf("hash get: hash = %d, it = %p, keylen = %d\n", state.hash, it, htons(pkt->mcr.request.keylen));
        state.it = it;

        output switch { case it: out(); else: null(); }
                    ''')


    class HashGetDummy(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
        iokvs_message* pkt = state.pkt;
        uint8_t cmd = pkt->mcr.request.opcode;   

        if(cmd == PROTOCOL_BINARY_CMD_GET) {
          void* key = pkt->payload + pkt->mcr.request.extlen;
          item* it = hasht_get(key, htons(pkt->mcr.request.keylen), state.hash);
          if(it) item_unref(it);
        }

        output { out(); }
                    ''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
//printf("hash put: hash = %d, it = %p\n", state.hash, state.it);
hasht_put(state.it, NULL);
output { out(); }
            ''')


    ######################## responses ########################

    class Scheduler(Element):

        def configure(self):
            self.out = Output(Size)

        def impl(self):
            self.run_c(r'''
static int core = -1;
core = (core + 1) %s %d;
output { out(core); }''' % ('%', n_cores))

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
//printf("size get\n");
    size_t msglen = sizeof(iokvs_message) + 4 + state.it->vallen;
    state.resp_size = msglen;
    state.vallen = state.it->vallen;
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
#ifndef CAVIUM
        memcpy(m, iokvs_template(), sizeof(iokvs_message));
#endif
        item* it = state.it;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_SUCCESS);

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = htonl(4 + state.vallen);
memcpy(m->payload + 4, item_value(it), state.vallen);

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
#ifndef CAVIUM
            memcpy(m, iokvs_template(), sizeof(iokvs_message));
#endif

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
//printf("size set\n");
            size_t msglen = sizeof(iokvs_message) + 4;
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
#ifndef CAVIUM
memcpy(m, iokvs_template(), sizeof(iokvs_message));
#endif

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = htons(%s);

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(msglen, m, pkt_buff); }
            ''' % self.status)

    class SizePktBuff(Element):
        def configure(self):
            self.inp = Input(Size)
            self.out = Output(Size, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''
            size_t msglen = inp();
            void* pkt = state.pkt;
            void* pkt_buff = state.pkt_buff;
            output { out(msglen, pkt, pkt_buff); }
            ''')

    class PrepareHeader(Element):
        def configure(self):
            self.inp = Input(Size, Pointer(iokvs_message), "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
        (size_t msglen, iokvs_message* m, void* buff) = inp();

        struct eth_addr mymac = m->ether.dest;
        m->ether.dest = m->ether.src;
        m->ether.src = mymac;
        m->ipv4.dest = m->ipv4.src;
        m->ipv4.src = settings.localip;
        m->ipv4._len = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4._ttl = 64;
        m->ipv4._chksum = 0;
        //m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.dest_port = m->udp.src_port;
        m->udp.src_port = htons(11211);
        m->udp.len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.cksum = 0;

        output { out(msglen, (void*) m, buff); }
            ''')

    class PrepareHeaderCPU(Element):
        def configure(self):
            self.inp = Input(Size, Pointer(iokvs_message), "void *")
            self.out = Output(Size, "void *", "void *")

        def impl(self):
            self.run_c(r'''
        (size_t msglen, iokvs_message* m, void* buff) = inp();
        iokvs_message* pkt = state.pkt;

        struct eth_addr mymac = pkt->ether.dest;
        m->ether.dest = pkt->ether.src;
        m->ether.src = mymac;
        m->ipv4.dest = pkt->ipv4.src;
        m->ipv4.src = settings.localip;
        m->ipv4._len = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4._ttl = 64;
        m->ipv4._chksum = 0;

        m->udp.dest_port = pkt->udp.src_port;
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
    size_t msglen = state.resp_size;
    //printf("packet from CPU: size = %ld\n", msglen);

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
    printf("GET -- status: %d, len: %d, val:%d\n", m->mcr.request.status, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- status: %d, len: %d\n", m->mcr.request.status, m->mcr.request.bodylen);
#endif

output { out(msglen, (void*) m, buff); }
    ''')



    ######################## item ########################
    class GetItemSpec(Element):
        this = Persistent(ItemAllocators)

        def states(self, item_allocators):
            self.this = item_allocators

        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''
    iokvs_message* pkt = state.pkt;
    size_t totlen = htonl(pkt->mcr.request.bodylen) - pkt->mcr.request.extlen;

#ifdef CAVIUM
    item *it = ialloc_alloc(&this->ia[state.core], sizeof(item) + totlen, false);
#else
    item *it = ialloc_alloc(&this->ia[0], sizeof(item) + totlen, false);
#endif

    //printf("get item: totlen = %ld, it = %p\n", totlen, it);
    if(it) {
        it->refcount = 1;
        uint16_t keylen = htons(pkt->mcr.request.keylen);

        it->hv = state.hash;
        it->vallen = totlen - keylen;
        it->keylen = keylen;
        void* key = pkt->payload + pkt->mcr.request.extlen;
        memcpy(item_key(it), key, totlen);
        state.it = it;
    }

    output switch { case it: out();  else: nothing(); }
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
            self.run_c(r'''
state.pkt = NULL;
state.core = cvmx_get_core_num();
            ''')

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

    class CleanLog(Element):
        this = Persistent(ItemAllocators)

        def states(self):
            self.this = item_allocators

        def impl(self):
            self.run_c(r'''
    static __thread int count = 0;
    count++;
    if(count == 32) {
      count = 0;
      clean_log(&this->ia[state.core], state.pkt == NULL);
    }
            ''')

    class CPUDummy(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            void* pkt = state.pkt;
            printf("cpu: hash = %d\n", state.hash);
            ''')

    def impl(self):

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 128 * 192, n_cores, 1, overlap=192, #64
                                                        enq_output=True, enq_blocking=True, enq_atomic=False)  # enq_blocking=False?
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 512 * 192, n_cores, 1, overlap=192, #160
                                                        enq_blocking=True, enq_output=True, deq_atomic=False)
        tx_enq = TxEnq()
        tx_deq = TxDeq()

        ######################## CPU #######################
        class process_eq(API):
            def configure(self):
                self.inp = Input(Size)

            def impl(self):
                classifier = main.Classifer()
                prepare_header = [main.PrepareHeaderCPU() for i in range(4)]
                save_response = main.SaveResponse()

                self.inp >> rx_deq
                rx_deq.out[0] >> classifier

                # get
                hash_get = main.HashGet()
                classifier.out_get >> hash_get
                hash_get.out >> main.SizeGetResp() >> main.Malloc() >> main.PrepareGetResp() >> prepare_header[0]
                hash_get.null >> main.SizeGetNullResp() >> main.Malloc() >> main.PrepareGetNullResp() >> prepare_header[1]

                # set
                get_item = main.GetItemSpec(states=[item_allocators_cpu])
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                classifier.out_set >> get_item >> main.HashPut() >> main.SizeSetResp() >> main.Malloc() \
                >> set_response >> prepare_header[2]

                # set (unseccessful)
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                get_item.nothing >> main.SizeSetResp() >> main.Malloc() >> set_reponse_fail >> prepare_header[3]

                for i in range(4):
                    prepare_header[i] >> save_response
                save_response >> tx_enq.inp[0]
                tx_enq.done >> main.Unref() >> main.Free()

        ####################### NIC Tx #######################
        class nic_tx(InternalLoop):
            def impl(self):
                scheduler = main.Scheduler()
                to_net = net_real.ToNet('to_net', configure=['from_net'])
                display = main.PrintMsg()
                hton = net_real.HTON(configure=['iokvs_message'])
                extract_pkt = main.ExtractPkt()

                scheduler >> tx_deq
                tx_deq.out[0] >> extract_pkt >> display >> hton >> to_net


        ######################## NIC Rx #######################
        class process_one_pkt(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet('from_net')
                from_net_free = net_real.FromNetFree('from_net_free')
                to_net = net_real.ToNet('to_net', configure=['from_net'])
                classifier = main.Classifer()
                check_packet = main.CheckPacket()
                cache = main.CacheSimulator()
                hton1 = net_real.HTON(configure=['iokvs_message'])
                hton2 = net_real.HTON(configure=['iokvs_message'])

                prepare_header = main.PrepareHeader()
                display = main.PrintMsg()
                drop = main.Drop()

                # from_net
                from_net >> hton1 >> check_packet >> main.SaveState() >> main.JenkinsHash() >> cache
                cache.out_miss >> main.HashGetDummy() >> rx_enq >> main.GetPktBuff() >> from_net_free
                cache.out_hit >> classifier
                from_net.nothing >> drop

                # get
                hash_get = main.HashGet()
                get_response = main.PrepareGetResp()
                classifier.out_get >> hash_get >> main.SizeGetResp() >> main.SizePktBuff() >> get_response >> prepare_header
                get_response >> main.Unref() >> library_dsl2.Drop()

                # get (null)
                hash_get.null >> main.SizeGetNullResp() >> main.SizePktBuff() >> main.PrepareGetNullResp() >> prepare_header

                # set
                get_item = main.GetItemSpec(states=[item_allocators])
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                classifier.out_set >> get_item >> main.HashPut() >> main.Unref() >> main.SizeSetResp() \
                >> main.SizePktBuff() >> set_response >> prepare_header

                # set (unseccessful)
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                get_item.nothing >> main.SizeSetResp() >> main.SizePktBuff() >> set_reponse_fail >> prepare_header

                # exception
                arp = main.HandleArp()
                check_packet.slowpath >> arp >> to_net
                arp.drop >> from_net_free
                check_packet.drop >> from_net_free

                # send
                prepare_header >> display >> hton2 >> to_net

                # clean log
                clean_log = main.CleanLog()

                run_order([to_net, from_net_free, drop], clean_log)

        process_one_pkt('process_one_pkt', device=target.CAVIUM, cores=range(n_cores))
        nic_tx('nic_tx', device=target.CAVIUM, cores=[n_cores])
        process_eq('process_eq', process='app')

class maintenance(InternalLoop):
    def impl(self):

        class Schedule(Element):
            def configure(self):
                self.out = Output(Int)

            def impl(self):
                self.run_c(r'''
                static int id = -1;
                id = (id + 1) %s %d;
                output { out(id); }
                ''' % ('%', n_cores))

        class Maintain(Element):
            this = Persistent(ItemAllocators)

            def configure(self):
                self.inp = Input(Int)
                self.this = item_allocators

            def impl(self):
                self.run_c(r'''
                int id = inp();
                ialloc_maintenance(&this->ia[id]);
                ''')

        Schedule() >> Maintain()

maintenance('maintenance', device=target.CAVIUM, cores=[11])


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.init = r'''
#ifdef CAVIUM
int corenum = cvmx_get_core_num();
settings_init();
if(corenum == 0) {
  ialloc_init();
  hasht_init();
}
#endif
'''
c.generate_code_as_header()
c.depend = {"test_app": ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'app']}
c.compile_and_run(["test_app"])
