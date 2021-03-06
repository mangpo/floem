from floem import *

n_cores = 11

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
    pkt = Field(Pointer(iokvs_message))
    pkt_buff = Field('void*')
    it = Field(Pointer(item), shared='data_region')
    key = Field('void*', size='state.pkt->mcr.request.keylen')
    hash = Field(Uint(32))
    core = Field(Uint(16))
    vallen = Field(Uint(32))


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
    state.pkt = m;
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
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, 'void*', 'void*')
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

    class SizeGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''
//printf("size get\n");
    size_t msglen = sizeof(iokvs_message) + 4 + state.it->vallen;
    state.vallen = state.it->vallen;
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
        //memcpy(m, &iokvs_template, sizeof(iokvs_message));
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
memcpy(m->payload + 4, item_value(it), state.vallen);

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
            //memcpy(m, &iokvs_template, sizeof(iokvs_message));

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
            void* pkt = state.pkt;
            void* pkt_buff = state.pkt_buff;
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
//memcpy(m, &iokvs_template, sizeof(iokvs_message));

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = %s;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(msglen, m, pkt_buff); }
            ''' % self.status)

    class SizePktBuff(Element):
        def configure(self):
            self.inp = Input(SizeT)
            self.out = Output(SizeT, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''
            size_t msglen = inp();
            void* pkt = state.pkt;
            void* pkt_buff = state.pkt_buff;
            output { out(msglen, pkt, pkt_buff); }
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
        //m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

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


    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output(SizeT, "void *", "void *")

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
        def states(self):
            self.this = item_allocators

        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''
    size_t totlen = state.pkt->mcr.request.bodylen - state.pkt->mcr.request.extlen;
    item *it = ialloc_alloc(&this->ia[state.core], sizeof(item) + totlen, false); // TODO
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


    class Unref(ElementOneInOut):
        def impl(self):
            self.run_c(r'''
        item_unref(state.it);
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

    def impl(self):

        ######################## NIC Rx #######################
        class process_one_pkt(Segment):
            def impl(self):
                from_net = net.FromNet('from_net')
                from_net_free = net.FromNetFree('from_net_free')
                to_net = net.ToNet('to_net', configure=['from_net'])
                classifier = main.Classifer()
                check_packet = main.CheckPacket()
                hton1 = net.HTON(configure=['iokvs_message'])
                hton2 = net.HTON(configure=['iokvs_message'])

                prepare_header = main.PrepareHeader()
                display = main.PrintMsg()
                drop = main.Drop()

                # from_net
                from_net >> hton1 >> check_packet >> main.SaveState() \
                >> main.GetKey() >> main.JenkinsHash() >> classifier
                from_net.nothing >> drop

                # get
                hash_get = main.HashGet()
                get_response = main.PrepareGetResp()
                classifier.out_get >> hash_get >> main.SizeGetResp() >> main.SizePktBuff() >> get_response >> prepare_header
                get_response >> main.Unref() >> library.Drop()

                # get (null)
                hash_get.null >> main.SizeGetNullResp() >> main.SizePktBuff() >> main.PrepareGetNullResp() >> prepare_header

                # set
                get_item = main.GetItemSpec()
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


class maintenance(Segment):
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
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.init = r'''
int corenum = cvmx_get_core_num();
settings_init();
if(corenum == 0) {
  ialloc_init();
  hasht_init();
}
'''
c.generate_code_as_header()
