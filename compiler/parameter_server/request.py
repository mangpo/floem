from message import *
import net, library
import sys

machine_id = int(sys.argv[1])

define_state(param_message)

class StatOne(State):
    starttime = Field('struct timeval')
    rtt_time = Field(Uint(64))
    rtt_count = Field(Int)
    freq_time = Field('struct timeval')
    freq_count = Field(Int)
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

int machine_id = %d;
m->ether.src = src[machine_id];
m->ether.dest = dest;

m->ipv4.src = src_ip[machine_id];
m->ipv4.dest = dest_ip;

static __thread uint16_t sport = 0;
m->udp.src_port = state->core_id+1; //(++sport == 0 ? ++sport : sport);
m->udp.dest_port = htons(1234);
m->udp.len = htons(size - offsetof(udp_message, udp));
m->udp.cksum = 0;

m->ether.type = htons(ETHERTYPE_IPv4);
m->ipv4._proto = 17; // udp
m->ipv4._v_hl = 4 << 4 | 5; 
m->ipv4._id = 0; 
m->ipv4._offset = 0; 
m->ipv4._len = htons(size - offsetof(udp_message, ipv4));
m->ipv4._ttl = 64;
m->ipv4._chksum = 0;

output { out(size, pkt, buff); }
        ''' % machine_id)


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
param_msg->member_id = state->core_id + OFFSET;
param_msg->start_id = worker->group_id * BUFFER_SIZE;
param_msg->n = BUFFER_SIZE;
int i;
for(i=0; i<BUFFER_SIZE; i++)
    param_msg->parameters[i] = rand();

#ifdef DEBUG
        printf("send: worker = %d, group_id = %d\n", state->core_id, worker->group_id);
        fflush(stdout);
#endif

worker->group_id++;
if(worker->group_id > N_GROUPS) {
    worker->group_id = 0;
    
    worker->freq_count++;
    if(worker->freq_count == 100) {
        struct timeval now;
        gettimeofday(&now, NULL);
        uint64_t t;
        t = (now.tv_sec - worker->freq_time.tv_sec) * 1000000 + (now.tv_usec - worker->freq_time.tv_usec);
        printf("[%d] rounds/s %f\n", state->core_id, 1000000.0 * worker->freq_count/t);
        
        worker->freq_time = now;
        worker->freq_count = 0;
    }
    
    // start timer, reset collector
    gettimeofday(&worker->starttime, NULL);
}

gettimeofday(&param_msg->starttime, NULL);

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
        
        //usleep(1);
bool yes = false;

state->core_id = core_id;
StatOne* worker = &this->workers[core_id];
if(worker->group_id > 0) 
    yes = true;
else {
    __SYNC;
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t t;
    t = (now.tv_sec - worker->starttime.tv_sec) * 1000000 + (now.tv_usec - worker->starttime.tv_usec);
    
    if(worker->total == 0 || t > TIMEOUT) {
        if(worker->total != 0) printf(">>> TIMEOUT total = %d (%d)\n", worker->total, core_id);
        //else printf(">>> COMPLETE (%d)\n", core_id);
        fflush(stdout);

        yes = true;
        memset(worker->groups, 0, sizeof(bool) * (N_GROUPS+1));
        worker->total = N_GROUPS;
        worker->group_id = 1;
        __SYNC;
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
    StatOne* worker = &this->workers[param_msg->member_id - OFFSET];
    
    struct timeval now;
    uint64_t rtt;
    gettimeofday(&now, NULL);
    rtt = (now.tv_sec - param_msg->starttime.tv_sec) * 1000000 + (now.tv_usec - param_msg->starttime.tv_usec);
                    
    worker->rtt_time += rtt;
    worker->rtt_count++;
        
/*
    if(rtt > 1000) {
        printf("slow: %ld\n", rtt);
    }
  */      
    
        if(worker->rtt_count == 100000) {
        printf("Latency: core = %d, time = %f\n", param_msg->member_id, 1.0*worker->rtt_time/worker->rtt_count);
        worker->rtt_time = 0;
        worker->rtt_count = 0;
    }
    

#ifdef DEBUG
        printf("update: worker = %d, group_id = %d\n", param_msg->member_id, param_msg->group_id);
#endif
    
    if(worker->groups[param_msg->group_id] == 0) {
        worker->groups[param_msg->group_id] = 1;
        int total = __sync_fetch_and_sub32(&worker->total, 1);
#ifdef DEBUG
        printf("total = %d (%d)\n", total, param_msg->member_id);
        fflush(stdout); 
#endif
        
    }
}

output { out(pkt, buff); }
        ''')

class Filter(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.other = Output("void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();

#define IP_PROTOCOL_POS 23

uint8_t* pkt_ptr = pkt;
bool pass = false;
udp_message* m = (udp_message*) pkt;

if(size == sizeof(udp_message) + sizeof(param_message) + BUFFER_SIZE * sizeof(int) &&
        m->ipv4._proto == 17 && 
        m->ether.type == htons(ETHERTYPE_IPv4)
        ) {
        pass = true;
} else {
        //printf("filter\n");
}

output switch {
    case pass: out(size, pkt, buff);
    else: other(pkt, buff);
}
        ''')

class MyState(State):
    core_id = Field(Int)

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class gen(Pipeline):
            def impl(self):
                net_alloc = net.NetAlloc()
                to_net = net.ToNet(configure=["net_alloc",1])

                self.core_id >> Wait() >> net_alloc
                net_alloc.oom >> library.Drop()
                net_alloc.out >> Request() >> PayloadGen() >> to_net

        class recv(Pipeline):
            def impl(self):
                from_net = net.FromNet(configure=[32])
                free = net.FromNetFree()
                filter = Filter()
                drop = library.Drop()

                from_net >> filter >> Reply() >> free
                from_net.nothing >> drop
                filter.other >> drop


        gen('gen', process='dpdk', cores=range(n_workers/2))
        recv('recv', process='dpdk', cores=range(1))


c = Compiler(main)
c.include = r'''
#include <string.h>
#include "protocol_binary.h"
#include <rte_ip.h>

struct eth_addr src[2] = { 
    {.addr = "\x3c\xfd\xfe\xaa\xd1\xe1"}, // guanaco -- 0
    {.addr = "\x3c\xfd\xfe\xad\x84\x8d"}, // dikdik -- 1
};

struct ip_addr src_ip[2] = { 
    {.addr = "\x0a\x64\x14\x08"}, // guanaco
    {.addr = "\x0a\x64\x14\x05"}, // dikdik
};

//struct eth_addr src = { .addr = "\x3c\xfd\xfe\xad\x84\x8d" }; // dikdik
//struct eth_addr dest = { .addr = "\x3c\xfd\xfe\xad\xfe\x05" }; // fossa
//struct eth_addr src = { .addr = "\x3c\xfd\xfe\xaa\xd1\xe1" }; // guanaco
struct eth_addr dest = { .addr = "\x68\x05\xca\x33\x13\x41" }; // hippopotamus
//struct eth_addr dest = { .addr = "\x02\x78\x1f\x5a\x5b\x01" }; // jaguar


//struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x05" };   // dikdik
//struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x07" }; // fossa
//struct ip_addr src_ip = { .addr = "\x0a\x64\x14\x08" };   // guanaco
struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x09" }; // hippopotamus
//struct ip_addr dest_ip = { .addr = "\x0a\x64\x14\x0b" }; // jaguar

static inline uint64_t rdtsc(void)
{
  uint32_t eax, edx;
  __asm volatile ("rdtsc" : "=a" (eax), "=d" (edx));
  return ((uint64_t)edx << 32) | eax;
}

//#define DEBUG
#define OFFSET %d

''' % (machine_id * n_workers/2) + define
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
