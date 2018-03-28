from common import *
import net, library

n_params = 1024
n_groups = 128
n_workers = 4
buffer_size = 32

define = r'''
#define N_PARAMS %d
#define N_GROUPS %d
#define BUFFER_SIZE %d
#define BITMAP_FULL 0xf
''' % (n_params, n_groups, buffer_size)

define_state(param_message)
define_state(param_message_out)

class Stat(State):
    starttime = Field(Uint(64))
    time = Field(Uint(64))
    count = Field(Int)
    groups = Field(Array(Bool, n_groups))

class StatAll(State):
    workers = Field(Array(State, n_workers))

stat_all = StatAll()

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

class Wait(Element):
    stat = Persistent(StatAll)

    def configure(self):
        self.inp = Input()
        self.out = Output()
        self.stat = stat_all

    def impl(self):
        self.run_c(r'''
bool yes = false;

StatOne* worker = &stat->workers[state->core_id];
if(worker->group_id > 0) 
    yes = true;
else {
    int i;
    yes = true;
    for(i=0; i<N_GROUPS; i++) {
        if(!worker->groups[i]) {
            yes = false;
            break;
        }
    }
    
    if(yes) {
        uint64_t t;
        t = rdtsc() - worker->starttime;
        worker->time += t;
        worker->count += 1;
        
        if(worker->count == 10) {
            print("Latency: core = %d, time = %ld\n", state->core_id, worker->time/worker->count);
            worker->time = 0;
            worker->count = 0;
        }
    }
}

output switch {
    case yes: out();
}
        ''')

class PayloadGen(Element):
    stat = Persistent(StatAll)

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.stat = stat_all


    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();

udp_message* m = (udp_message*) pkt;
param_message* param_msg = (param_message*) m->payload;

StatOne* worker = &stat->workers[state->core_id];

param_msg->group_id = worker->group_id;
param_msg->member_id = state->core_id;
param_msg->start_id = group_id * BUFFER_SIZE;
param_msg->n = BUFFER_SIZE;
int i;
for(i=0; i<BUFFER_SIZE; i++)
    param_msg->parameters[i] = rand();

worker->group_id++;
if(worker->group_id >= N_GROUPS) {
    worker->group_id = 0;
    
    // start timer, reset collector
    memset(worker->groups, 0, sizeof(bool) * N_GROUPS);
    worker->starttime = rdtsc();
}

output { out(size, pkt, buff); }
        ''')

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
        //printf("pkt %ld\n", size);
uint64_t mycount = __sync_fetch_and_add64(&this->count, 1);
        if(mycount == 100000) {
    struct timeval now;
    gettimeofday(&now, NULL);
    size_t thistime = now.tv_sec * 1000000 + now.tv_usec;
    printf("%zu pkts/s  %f Gbits/s\n", (mycount * 1000000)/(thistime - this->lasttime),
                                        (mycount * size * 8.0)/((thistime - this->lasttime) * 1000));
    this->lasttime = thistime;
    this->count = 0;
}
}

output { out(pkt, buff); }
        ''')


class gen(Pipeline):
    def impl(self):
        net_alloc = net.NetAlloc()
        to_net = net.ToNet(configure=["net_alloc"])

        # TODO: start from Wait

        library.Constant(configure=[SizeT,80]) >> net_alloc
        net_alloc.oom >> library.Drop()
        net_alloc.out >> Request() >> PayloadGen() >> to_net

class recv(Pipeline):
    def impl(self):
        from_net = net.FromNet()
        free = net.FromNetFree()

        from_net.nothing >> library.Drop()

        from_net >> Reply() >> free

        # TODO

n = 5
gen('gen', process='dpdk', cores=range(n))
recv('recv', process='dpdk', cores=range(n))
c = Compiler()
c.include = r'''
#include <string.h>
#include "protocol_binary.h"
#include <rte_ip.h>

struct eth_addr src = { .addr = "\x3c\xfd\xfe\xad\x84\x8d" }; // dikdik
struct eth_addr dest = { .addr = "\x3c\xfd\xfe\xad\xfe\x05" }; // fossa

struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x05" };   // dikdik
struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x07" }; // fossa
'''
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
