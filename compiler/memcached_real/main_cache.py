from floem import *
from compiler import Compiler
import net, cache_smart, queue_smart, library

n_cores = 1
nic_threads = 4
#mode = 'dpdk'
mode = target.CAVIUM

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


CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, CacheState = \
    cache_smart.smart_cache_with_state('MyCache',
                                       (Pointer(Int),'key','keylen'), [(Pointer(Int),'val','vallen')],
                                       var_size=True, hash_value='hash',
                                       write_policy=Cache.write_through, write_miss=Cache.no_write_alloc)


class item(State):
    next = Field('struct _item')
    hv = Field(Uint(32))
    vallen = Field(Uint(32))
    refcount = Field(Uint(16))
    keylen = Field(Uint(16))
    flags = Field(Uint(32))

    def init(self): self.declare = False

class MyState(CacheState):
    pkt = Field(Pointer(iokvs_message))
    pkt_buff = Field('void*')
    it = Field(Pointer(item))
    hash = Field(Uint(32))
    keylen = Field(Uint(32))
    key = Field('void*', size='state->keylen')
    vallen = Field(Uint(32))
    val = Field('void*', size='state->vallen')

class Schedule(State):
    core = Field(Int)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field('struct item_allocator*')

    def init(self):
        self.ia = 'get_item_allocators()'

item_allocators = ItemAllocators()

class segments_holder(State):
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    offset = Field(Uint(64))
    next = Field('struct _segments_holder*')
    last = Field('struct _segments_holder*')

class main(Flow):
    state = PerPacket(MyState)

    class SaveState(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    (size_t size, void* pkt, void* buff) = inp();
    iokvs_message* m = (iokvs_message*) pkt;
    state->pkt = m;
    state->pkt_buff = buff;
    output { out(); }
                ''')

    class GetPktBuff(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output("void*", "void*")

        def impl(self):
            self.run_c(r'''
    void* pkt = state->pkt;
    void* pkt_buff = state->pkt_buff;
    output { out(pkt, pkt_buff); }
            ''')

    class CheckPacket(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, 'void*', 'void*')
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
            self.out_get = Output('uint8_t*', Int)
            self.out_set = Output('uint8_t*', Int, Int, 'uint8_t*')

        def impl(self):
            self.run_c(r'''
uint8_t cmd = state->pkt->mcr.request.opcode;
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
state->key = state->pkt->payload + state->pkt->mcr.request.extlen;
output { out(); }''')

    class TxScheduler(Element):
        def configure(self):
            self.inp = Input(Int)
            self.out = Output(Int)

        def impl(self):
            self.run_c(r'''
            (int id) = inp();
            int qid = id %s %d;
            output { out(qid); }
            ''' % ('%', n_cores))


    ######################## hash ########################

    class JenkinsHash(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
state->hash = jenkins_hash(state->key, state->pkt->mcr.request.keylen);
//printf("hash = %d\n", hash);
output { out(); }
            ''')

    class QID(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    state->qid = state->hash %s %d;
    output { out(); }
    ''' % ('%', n_cores))

    class HashGet(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output()

        def impl(self):
            self.run_c(r'''
item* it = hasht_get(state->key, state->keylen, state->hash);
printf("hash get\n");
state->it = it;

if(it) {
    state->val = item_value(it);
    state->vallen = it->vallen;
} else {
    state->vallen = 0;
}

output { out(); }
            ''')

    class GetResult(Element):
        def configure(self):
            self.inp = Input()
            self.hit = Output()
            self.miss = Output()

        def impl(self):
            self.run_c(r'''
bool yes = (state->vallen > 0);

output switch { case yes: hit(); else: miss(); }
            ''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
printf("hash put\n");
if(state->it) hasht_put(state->it, NULL);
output { out(); }
            ''')


    ######################## responses ########################

    class Scheduler(Element):
        this = Persistent(Schedule)

        def configure(self):
            self.out = Output(Int)
            self.this = Schedule()

        def impl(self):
            self.run_c(r'''
this->core = (this->core + 1) %s %s;
output { out(this->core); }''' % ('%', n_cores))

    class SizeGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''
//printf("size get\n");
    size_t msglen = sizeof(iokvs_message) + 4 + state->vallen;
    output { out(msglen); }
            ''')

    class PrepareGetResp(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
        (size_t msglen, void* pkt, void* pkt_buff) = inp();

        iokvs_message *m = pkt;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_SUCCESS;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state->vallen;
memcpy(m->payload + 4, state->val, state->vallen);

output { out(msglen, m, pkt_buff); }
            ''')

    class SizeGetNullResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''
//printf("size get null\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }
            ''')

    class PrepareGetNullResp(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''
            (size_t msglen, void* pkt, void* pkt_buff) = inp();
            iokvs_message *m = pkt;

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
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''
//printf("size set\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }
            ''')

    class SizePktBuffSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''
            size_t msglen = sizeof(iokvs_message) + 4;
            void* pkt = state->pkt;
            void* pkt_buff = state->pkt_buff;
            output { out(msglen, pkt, pkt_buff); }
            ''')

    class PrepareSetResp(Element):
        def configure(self, status):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')
            self.status = status
            # PROTOCOL_BINARY_RESPONSE_SUCCESS
            # PROTOCOL_BINARY_RESPONSE_ENOMEM

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* pkt_buff) = inp();
iokvs_message *m = pkt;

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = %s;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(msglen, m, pkt_buff); }
            ''' % self.status)

    class PktBuff(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output('void*', 'void*')

        def impl(self):
            self.run_c(r'''
            void* pkt = state->pkt;
            void* pkt_buff = state->pkt_buff;
            output { out(pkt, pkt_buff); }
            ''')

    class PrepareHeader(Element):
        def configure(self):
            self.inp = Input(SizeT, Pointer(iokvs_message), "void *")
            self.out = Output(SizeT, "void *", "void *")

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

        m->udp.dest_port = m->udp.src_port;
        m->udp.src_port = htons(11211);
        m->udp.len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.cksum = 0;

        output { out(msglen, (void*) m, buff); }
            ''')

    class HandleArp(Element):
        def configure(self):
            self.inp = Input("void *", "void *")
            self.out = Output(SizeT, "void *", "void *")
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

    }

    output switch { 
      case resp: out(sizeof(struct eth_hdr) + sizeof(struct arp_hdr), pkt, buff); 
            else: drop(pkt, buff);
    }
            ''')


    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output(SizeT, "void *", "void *")

        def impl(self):
            self.run_c(r'''
(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;
uint8_t *val = m->payload + 4;
uint8_t opcode = m->mcr.request.opcode;

/*
if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- status: %d, len: %d, val:%d\n", m->mcr.request.status, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- status: %d, len: %d\n", m->mcr.request.status, m->mcr.request.bodylen);
*/

output { out(msglen, (void*) m, buff); }
    ''')



    ######################## item ########################
    class KV2State(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
        uint8_t *p = state->key;
        size_t totlen = state->pkt->mcr.request.bodylen - state->pkt->mcr.request.extlen;
        uint16_t keylen = state->pkt->mcr.request.keylen;
        
        state->keylen = keylen;
        state->vallen = totlen - keylen;
        state->val = (void*) (p + keylen);
        output { out(); }
            ''')

    class GetItemSpec(Element):
        this = Persistent(ItemAllocators)
        def states(self):
            self.this = item_allocators

        def configure(self):
            self.inp = Input()
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    size_t totlen = state->keylen + state->vallen;
    item *it = ialloc_alloc(&this->ia[state->qid], sizeof(item) + totlen, false); // TODO
    if(it) {
        it->refcount = 1;
        uint16_t keylen = state->keylen;

        it->hv = state->hash;
        it->vallen = state->vallen;
        it->keylen = state->keylen;
        memcpy(item_key(it), state->key, state->keylen);
        memcpy(item_value(it), state->val, state->vallen);
        state->it = it;
    } else {
        state->keylen = 0;
    }

    output { out(); }
            ''')

    class SetResult(Element):
        def configure(self):
            self.inp = Input()
            self.success = Output()
            self.fail = Output()

        def impl(self):
            self.run_c(r'''
    bool yes = (state->keylen > 0);
    output switch { case yes: success(); else: fail(); }
            ''')

    class Key2State(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
    state->it = NULL;
    state->keylen = state->pkt->mcr.request.keylen;
    output { out(); }
    ''')

    class Unref(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
    if(state->it) item_unref(state->it);
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

    class CleanLog(Element):
        this = Persistent(ItemAllocators)

        def states(self):
            self.this = item_allocators

        def configure(self):
            self.inp = Input(Int)
            self.out = Output(Int)

        def impl(self):
            self.run_c(r'''
    (int id) = inp();
    
    static __thread int count = 0;
    count++;
    if(count == 32) {
      count = 0;
      clean_log(&this->ia[id], true); // pkt = NULL
    }
    
    output { out(id); }
            ''')

    def impl(self):

        # Queue
        RxEnq, RxDeq, RxScan = queue_smart.smart_queue("rx_queue", entry_size=192, size=256, insts=n_cores,
                                                       channels=2, enq_blocking=True, enq_atomic=True, enq_output=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        TxEnq, TxDeq, TxScan = queue_smart.smart_queue("tx_queue", entry_size=192, size=256, insts=n_cores,
                                                       channels=2, checksum=True, enq_blocking=True, deq_atomic=True,
                                                       enq_output=True)
        tx_enq = TxEnq()
        tx_deq = TxDeq()

        ######################## CPU #######################
        class process_one_pkt(Pipeline):
            def impl(self):
                self.core_id >> main.CleanLog() >> rx_deq
                rx_deq.out[0] >> main.HashGet() >> tx_enq.inp[0]
                rx_deq.out[1] >> main.GetItemSpec() >> main.HashPut() >> tx_enq.inp[1]
                tx_enq.done >> main.Unref() >> library.Drop()


        ######################## NIC #######################
        class nic_rx(Pipeline):
            def impl(self):
                from_net = net.FromNet('from_net')
                from_net_free = net.FromNetFree('from_net_free')
                to_net = net.ToNet('to_net', configure=['from_net'])
                classifier = main.Classifer()
                check_packet = main.CheckPacket()
                hton = net.HTON(configure=['iokvs_message'])
                arp = main.HandleArp()
                drop = main.Drop()

                # from_net
                from_net >> hton >> check_packet >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> classifier
                from_net.nothing >> drop

                classifier.out_get >> main.Key2State() >> CacheGetStart() >> main.QID() >> rx_enq.inp[0]
                classifier.out_set >> main.KV2State() >> CacheSetStart() >> main.QID() >> rx_enq.inp[1]
                rx_enq >> main.PktBuff() >> from_net_free

                # exception
                check_packet.slowpath >> arp >> to_net
                arp.drop >> from_net_free
                check_packet.drop >> from_net_free

        class nic_tx(Pipeline):
            def impl(self):
                prepare_header = main.PrepareHeader()
                get_result = main.GetResult()
                get_response = main.PrepareGetResp()
                get_response_null = main.PrepareGetNullResp()
                set_result = main.SetResult()
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                hton = net.HTON(configure=['iokvs_message'])
                to_net = net.ToNet('to_net', configure=['from_net'])

                net_allocs = [net.NetAlloc() for i in range(4)]
                drop = library.Drop()

                self.core_id >> main.TxScheduler() >> tx_deq
                
                # get
                tx_deq.out[0] >> CacheGetEnd() >> get_result
                get_result.hit >> main.SizeGetResp() >> net_allocs[0] >> get_response >> prepare_header
                get_result.miss >> main.SizeGetNullResp() >> net_allocs[1] >> get_response_null >> prepare_header

                # set
                tx_deq.out[1] >> CacheSetEnd() >> set_result
                set_result.success >> main.SizeSetResp() >> net_allocs[2] >> set_response >> prepare_header
                set_result.fail >> main.SizeSetResp() >> net_allocs[3] >> set_reponse_fail >> prepare_header

                # send
                prepare_header >> hton >> to_net

                for i in range(4):
                    net_allocs[i].oom >> drop

        if mode == 'dpdk':
            process_one_pkt('process_one_pkt', process=target.dpdk, cores=range(n_cores))
            nic_rx('nic_rx', process=target.dpdk, cores=[nic_threads + x for x in range(nic_threads)])
            nic_tx('nic_tx', process=target.dpdk, cores=range(nic_threads))
        else:
            process_one_pkt('process_one_pkt', process='app', cores=range(n_cores))
            nic_rx('nic_rx', device=target.CAVIUM, cores=[nic_threads + x for x in range(nic_threads)])
            nic_tx('nic_tx', device=target.CAVIUM, cores=range(nic_threads))


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "iokvs.h"
#include "protocol_binary.h"
'''
if mode == target.CAVIUM:
    c.init = r'''
#ifdef CAVIUM
    settings_init();
#endif
    '''
    c.generate_code_as_header()
    c.depend = ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'app']
else:
    c.generate_code_as_header()
    c.depend = ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'dpdk']
c.compile_and_run('test_cache')
