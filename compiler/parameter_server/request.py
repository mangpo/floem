from message import *
import net, library

define_state(param_message)

class StatOne(State):
    starttime = Field(Uint(64))
    time = Field(Uint(64))
    count = Field(Int)
    total = Field(Int)
    group_id = Field(Int)
    groups = Field(Array(Bool, n_groups+1)) # group_id starts from 1

class StatAll(State):
    workers = Field(Array(StatOne, n_workers))

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
        //m->ipv4._chksum = rte_ipv4_cksum(&m->ipv4);  // TODO

        m->udp.len = htons(size - offsetof(udp_message, udp));
        m->udp.cksum = 0;
        //printf("size: %ld %ld %ld\n", size, m->ipv4._len, m->udp.len);

output { out(size, pkt, buff); }
        ''')


class PayloadGen(Element):
    this = Persistent(StatAll)

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.this = stat_all


    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();

udp_message* m = (udp_message*) pkt;
param_message* param_msg = (param_message*) m->payload;

StatOne* worker = &this->workers[state->core_id];

param_msg->group_id = worker->group_id;
param_msg->member_id = state->core_id;
param_msg->start_id = worker->group_id * BUFFER_SIZE;
param_msg->n = BUFFER_SIZE;
int i;
for(i=0; i<BUFFER_SIZE; i++)
    param_msg->parameters[i] = rand();

#ifdef DEBUG
        printf("send: worker = %d, group_id = %d\n", state->core_id, worker->group_id);
#endif

worker->group_id++;
if(worker->group_id > N_GROUPS) {
    worker->group_id = 0;
    
    // start timer, reset collector
    worker->starttime = rdtsc();
}

output { out(size, pkt, buff); }
        ''')


class Wait(Element):
    this = Persistent(StatAll)

    def configure(self):
        self.inp = Input(Int)
        self.out = Output(SizeT)
        self.this = stat_all

    def impl(self):
        self.run_c(r'''
(int core_id) = inp();

#define TIMEOUT 10000000
        
bool yes = false;

state->core_id = core_id;
StatOne* worker = &this->workers[core_id];
if(worker->group_id > 0) 
    yes = true;
else {
    if(worker->total == 0 ||
       rdtsc() - worker->starttime > TIMEOUT) {
        yes = true;
        memset(worker->groups, 0, sizeof(bool) * (N_GROUPS+1));
        worker->total = N_GROUPS;
        worker->group_id = 1;
    }
}
int size = sizeof(udp_message) + sizeof(param_message) + BUFFER_SIZE * sizeof(int);

output switch {
    case yes: out(size);
}
        ''')


class Reply(Element):
    this = Persistent(StatAll)

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output("void*", "void*")

    def states(self):
        self.this = stat_all

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
udp_message* m = (udp_message*) pkt;

if(m->ipv4._proto == 17) {
    udp_message* m = (udp_message*) pkt;
    param_message* param_msg = (param_message*) m->payload;
    StatOne* worker = &this->workers[param_msg->member_id];

#ifdef DEBUG
        printf("update: worker = %d, group_id = %d\n", param_msg->member_id, param_msg->group_id);
#endif
    
    if(worker->groups[param_msg->group_id] == 0) {
        worker->groups[param_msg->group_id] = 1;
        int total = __sync_fetch_and_sub32(&worker->total, 1);
#ifdef DEBUG
        printf("total = %d\n", total);
#endif
        
        if(total == 1) {
            uint64_t t;
            t = rdtsc() - worker->starttime;
            worker->time += t;
            worker->count += 1;

            if(worker->count == 1000) {
                printf("Latency: core = %d, time = %f\n", param_msg->member_id, 1.0*worker->time/worker->count);
                worker->time = 0;
                worker->count = 0;
            }
        }
    }
}

output { out(pkt, buff); }
        ''')

class MyState(State):
    core_id = Field(Int)

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class gen(Pipeline):
            def impl(self):
                net_alloc = net.NetAlloc()
                to_net = net.ToNet(configure=["net_alloc"])

                self.core_id >> Wait() >> net_alloc
                net_alloc.oom >> library.Drop()
                net_alloc.out >> Request() >> PayloadGen() >> to_net

        class recv(Pipeline):
            def impl(self):
                from_net = net.FromNet()
                free = net.FromNetFree()

                from_net.nothing >> library.Drop()
                from_net >> Reply() >> free

        n = 1  # number of workers
        gen('gen', process='dpdk', cores=range(n))
        recv('recv', process='dpdk', cores=range(n))

c = Compiler(main)
c.include = r'''
#include <string.h>
#include "protocol_binary.h"
#include <rte_ip.h>

//struct eth_addr src = { .addr = "\x3c\xfd\xfe\xad\x84\x8d" }; // dikdik
struct eth_addr src = { .addr = "\x3c\xfd\xfe\xaa\xd1\xe1" }; // guanaco
//struct eth_addr dest = { .addr = "\x3c\xfd\xfe\xad\xfe\x05" }; // fossa
struct eth_addr dest = { .addr = "\x68\x05\xca\x33\x13\x41" }; // hippopotamus

//struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x05" };   // dikdik
struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x08" };   // guanaco
//struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x07" }; // fossa
struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x09" }; // hippopotamus

static inline uint64_t rdtsc(void)
{
  uint32_t eax, edx;
  __asm volatile ("rdtsc" : "=a" (eax), "=d" (edx));
  return ((uint64_t)edx << 32) | eax;
}

''' + define
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
