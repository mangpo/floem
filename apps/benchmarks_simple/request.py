from dsl import *
from compiler import Compiler
import target, queue, net, library


class Request(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;

m->ether.src = src;
m->ether.dest = dest;

m->ipv4.src = src_ip;
m->ipv4.dest = dest_ip;

static __thread uint16_t sport = 0;
m->udp.src_port = (++sport == 0 ? ++sport : sport);
m->udp.dest_port = m->udp.src_port;

m->ether.type = htons(ETHERTYPE_IPv4);
m->ipv4._proto = 17;
        m->ipv4._len = htons(size - offsetof(iokvs_message, ipv4));
        m->ipv4._ttl = 64;
        m->ipv4._chksum = 0;
        //m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.len = htons(size - offsetof(iokvs_message, udp));
        m->udp.cksum = 0;
        //printf("sizeof(iokvs) = %d, size = %ld\n", sizeof(iokvs_message), size);

output { out(size, pkt, buff); }
        ''')

class Stat(State):
    count = Field(SizeT)
    lasttime = Field(SizeT)

    def init(self):
        self.count = 0
        self.lasttime = 0

class Reply(Element):
    this = Persistent(Stat)

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output("void*", "void*")

    def states(self):
        self.this = Stat()

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;


if(m->mcr.request.magic == PROTOCOL_BINARY_RES) {
    //printf("pkt\n");
uint64_t mycount = __sync_fetch_and_add64(&this->count, 1);
if(mycount == 5000000) {
    struct timeval now;
    gettimeofday(&now, NULL);
    size_t thistime = now.tv_sec * 1000000 + now.tv_usec;
    printf("%zu pkts/s\n", (mycount * 1000000)/(thistime - this->lasttime));
    this->lasttime = thistime;
    this->count = 0;
}
}

output { out(pkt, buff); }
        ''')


class gen(Segment):
    def impl(self):
        net_alloc = net.NetAlloc()
        to_net = net.ToNet(configure=["net_alloc"])

        library.Constant(configure=[SizeT,64]) >> net_alloc
        net_alloc.oom >> library.Drop()
        net_alloc.out >> Request() >> to_net

class recv(Segment):
    def impl(self):
        from_net = net.FromNet()
        free = net.FromNetFree()

        from_net.nothing >> library.Drop()

        from_net >> Reply() >> free

n = 5
gen('gen', process='dpdk', cores=range(n))
recv('recv', process='dpdk', cores=range(n))
c = Compiler()
c.include = r'''
#include "protocol_binary.h"

struct eth_addr src = { .addr = "\x3c\xfd\xfe\xaa\xd1\xe1" }; // guanaco
struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x08" };

struct eth_addr dest = { .addr = "\x02\x78\x1f\x5a\x5b\x01" }; // jaguar
struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x0b", };
'''
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
