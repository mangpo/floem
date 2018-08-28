from dsl import *
from compiler import Compiler
import target, queue, net, library

pkt_size = 80

class Request(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
udp_message* m = (udp_message*) pkt;

m->ether.src = src;
m->ether.dest = dest;

m->ipv4.src = src_ip;
m->ipv4.dest = dest_ip;

static __thread uint16_t sport = 0;
m->udp.src_port = (++sport == 0 ? ++sport : sport);
m->udp.dest_port = m->udp.src_port;

m->ether.type = htons(ETHERTYPE_IPv4);
m->ipv4._proto = 17; // udp
        m->ipv4._len = htons(size - offsetof(udp_message, ipv4));
        m->ipv4._ttl = 64;
        m->ipv4._chksum = 0;
        m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.len = htons(size - offsetof(udp_message, udp));
        m->udp.cksum = 0;
        //printf("size: %ld %ld %ld\n", size, m->ipv4._len, m->udp.len);

output { out(size, pkt, buff); }
        ''')

class PayloadGen(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();

udp_message* m = (udp_message*) pkt;
int i;

switch(CMD) {

case HASH:
strcpy(m->cmd, "HASH");
for(i=0; i< (size - sizeof(udp_message) - 5)/8; i++) {                            
    sprintf(m->payload + 8*i, "%d", TEXT_BASE + rand() % TEXT_BASE);          
}                                                                          
break;  

case FLOW:
strcpy(m->cmd, "FLOW");
for(i=0; i<4; i++) {
    sprintf(m->payload + 8*i, "%d", TEXT_BASE + rand() % TEXT_BASE);
}
break;

case SEQU:
strcpy(m->cmd, "SEQU");
sprintf(m->payload, "%d", 1000 + rand() % 1000);
break;

}

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
udp_message* m = (udp_message*) pkt;


if(m->ipv4._proto == 17) {
uint64_t mycount = __sync_fetch_and_add64(&this->count, 1);
        if(mycount == 5000000) {
    __sync_synchronize();
    size_t lasttime = this->lasttime;
    struct timeval now;
    gettimeofday(&now, NULL);
    size_t thistime = now.tv_sec * 1000000 + now.tv_usec;
    printf("%s pkts/s %s Gbits/s\n", (mycount * 1000000)/(thistime - lasttime),
        (mycount * %d * 8.0)/((thistime - lasttime) * 1000));
    this->lasttime = thistime;
    this->count = 0;
    __sync_synchronize();
}
}

output { out(pkt, buff); }
        ''' % ('%zu', '%f', pkt_size))


class gen(Pipeline):
    def impl(self):
        net_alloc = net.NetAlloc()
        to_net = net.ToNet(configure=["net_alloc"])

        library.Constant(configure=[SizeT,pkt_size]) >> net_alloc
        net_alloc.oom >> library.Drop()
        net_alloc.out >> Request() >> PayloadGen() >> to_net

class recv(Pipeline):
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
#include <string.h>
#include "protocol_binary.h"
#include <rte_ip.h>

//struct eth_addr src = { .addr = "\x3c\xfd\xfe\xaa\xd1\xe1" }; // guanaco
struct eth_addr dest = { .addr = "\x02\x78\x1f\x5a\x5b\x01" }; // jaguar
struct eth_addr src = { .addr = "\x3c\xfd\xfe\xaa\xd1\xe0" }; // guanaco
//struct eth_addr dest = { .addr = "\x68\x05\xca\x33\x13\x40" }; // hippo

//struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x08" }; // guanaco
struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x0b" }; // jauar
struct ip_addr src_ip = { .addr = "\x0a\x64\x0a\x08" }; // guanaco
//struct ip_addr dest_ip = { .addr = "\x0a\x64\x0a\x09" }; // hippo

#define TEXT_BASE 10000000 /* 10M (8 bits) */
typedef enum _TYPE {
    ECHO, /* echo */
    HASH, /* hash computing */
    FLOW, /* flow classification */
    SEQU, /* sequencer */
} PKT_TYPE;

#define CMD HASH
'''
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
