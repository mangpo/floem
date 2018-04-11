
from message import *
import net, library

nic = 'dpdk' #target.CAVIUM

addr = r'''
//#define DEBUG

static struct eth_addr mydests[2] = { 
    //{ .addr = "\x68\x05\xca\x33\x13\x41" }, // hippopotamus
    {.addr = "\x3c\xfd\xfe\xaa\xd1\xe1"}, // guanaco
    {.addr = "\x3c\xfd\xfe\xad\x84\x8d"}, // dikdik
};
    
static struct ip_addr myips[2] = { 
    //{ .addr = "\x0a\x64\x14\x09" }, // hippopotamus
    {.addr = "\x0a\x64\x14\x08"}, // guanaco
    {.addr = "\x0a\x64\x14\x05"}, // dikdik
};
'''

class MyState(State):
    pkt_buff = Field('void*')
    pkt = Field('void*')
    parameters = Field('int*')
    n = Field(Int)
    group_id = Field(Int)

define_state(param_message)

class param_aggregate(State):
    group_id = Field(Int)
    start_id = Field(Uint(64))
    n = Field(Int)
    bitmap = Field(Int)
    parameters = Field(Array(Int, buffer_size))
    layout = [group_id, start_id, n, bitmap, parameters]

class param_buffer(State):
    groups = Field(Array(param_aggregate, n_groups+1))

class param_store(State):
    parameters = Field(Array(Int, n_params))

    def init(self):
        self.parameters = lambda x: 'memset(%s, 0.5, N_PARAMS);' % x


param_buffer_inst = param_buffer()
param_store_inst = param_store()


class Aggregate(Element):
    buffer = Persistent(param_buffer)

    def configure(self):
        self.inp = Input("void*")
        self.up = Output("param_aggregate*")
        self.other = Output()
        self.buffer = param_buffer_inst

    def impl(self):
        self.run_c(r'''
(void* pkt) = inp();
udp_message* udp_msg = pkt;
param_message* param_msg = (param_message*) udp_msg->payload;

int group_id = nic_htonl(param_msg->group_id);
int key = group_id % N_GROUPS;
param_aggregate* agg = &buffer->groups[key];
int old_group_id = agg->group_id;

bool pass = true, update = false;
int bit, bitmap, new_bitmap;
int i;

if(old_group_id == 0) {
    if(__sync_bool_compare_and_swap32((uint32_t*) &agg->group_id, old_group_id, group_id)) {
        agg->start_id = nic_htonl(param_msg->start_id);
        agg->n = nic_htonl(param_msg->n);
    }
    else {
        __SYNC;
        if(agg->group_id != group_id)
            pass = false;
    }
}
else if(old_group_id != group_id) {
    pass = false;
}

#ifdef DEBUG
        printf("recv: worker = %d, group_id = %d, old_group_id = %d, pass = %d\n", 
        nic_htonl(param_msg->member_id), nic_htonl(param_msg->group_id), nic_htonl(old_group_id), pass);
#endif

if(pass) {
    bit = 1 << nic_htonl(param_msg->member_id);
    do {
        bitmap = agg->bitmap;
#ifdef DEBUG
        printf("bit = %x, bitmap = %x\n", bit, bitmap);
#endif
        if(bit & bitmap)
            new_bitmap = bit;
        else
            new_bitmap = bitmap | bit;
    } while(new_bitmap != bitmap && 
    !__sync_bool_compare_and_swap32((uint32_t*) &agg->bitmap, bitmap, new_bitmap));
    
    
    for(i=0; i<agg->n; i++) {
        __sync_fetch_and_add32(&agg->parameters[i], param_msg->parameters[i]);
    }

    //assert(new_bitmap == BITMAP_FULL);
        
    if(new_bitmap == BITMAP_FULL)
        update = true;
}

if(!pass) assert(0);


output switch {
    case update: up(agg);
    else: other();
}
        ''')


class UpdateParam(Element):
    buffer = Persistent(param_buffer)
    store = Persistent(param_store)

    def configure(self):
        self.inp = Input("param_aggregate*")
        self.out = Output(SizeT)
        self.buffer = param_buffer_inst
        self.store = param_store_inst


    def impl(self):
        self.run_c(r'''
(param_aggregate* agg) = inp();
int start_id = agg->start_id;

#ifdef DEBUG
        printf("update: group_id = %d\n", agg->group_id);
#endif

state->group_id = agg->group_id;
state->n = agg->n;
state->parameters = &store->parameters[start_id];

// Update params
int i;
for(i=0; i<agg->n; i++) {
    store->parameters[start_id] += agg->parameters[i] >> 8;   // learning_rate = 1/2^8
}

// Reset aggregrate buffer
memset(agg->parameters, 0, agg->n * sizeof(int));
agg->bitmap = 0;
agg->group_id = 0;

int size = sizeof(udp_message) + sizeof(param_message) + agg->n * sizeof(int);

output {
    out(size);
}
        ''')


class Copy(Element):
    def configure(self, worker_id):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.worker_id = worker_id

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
memcpy(pkt, state->pkt, sizeof(udp_message) + sizeof(param_message));
udp_message* old = state->pkt;
udp_message* m = pkt;

// fill in pkt
int id = %d;
int div = %d;
param_message* param_msg = (param_message*) m->payload;

param_msg->member_id = nic_htonl(id);
memcpy(param_msg->parameters, state->parameters, sizeof(int) * state->n);

// fill in MAC address
m->ether.src = old->ether.dest;
m->ether.dest = mydests[id/div];

m->ipv4.src = old->ipv4.dest;
m->ipv4.dest = myips[id/div];
#ifdef DEBUG
        printf("send pkt: worker = %s, group_id = %s\n", param_msg->member_id, param_msg->group_id);
#endif

output { out(size, pkt, buff); }
        ''' % (self.worker_id, n_workers/2, '%d', '%d'))


class Filter(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.other = Output("void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();

bool pass = false;
udp_message* m = (udp_message*) pkt;

if(size == sizeof(udp_message) + sizeof(param_message) + BUFFER_SIZE * sizeof(int) &&
        m->ipv4._proto == 17 && 
        m->ether.type == htons(ETHERTYPE_IPv4)
        ) {
        pass = true;
}

output switch {
    case pass: out(size, pkt, buff);
    else: other(pkt, buff);
}
        ''')


class SavePkt(Element):
    def configure(self):
        self.inp = Input(SizeT, "void *", "void *")
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''
    (size_t size, void* pkt, void* buff) = inp();
    state->pkt_buff = buff;
    state->pkt = pkt;
    output { out(pkt); }
                ''')

class GetPkt(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
    void* pkt = state->pkt;
    void* buff = state->pkt_buff;
    output { out(pkt, buff); }
        ''')

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class nic_rx(Pipeline):
            def impl(self):
                from_net = net.FromNet(configure=[32])
                to_net = net.ToNet(configure=["alloc",1])
                net_free = net.FromNetFree()

                filter = Filter()
                aggregate = Aggregate()
                update = UpdateParam()
                get_pkt = GetPkt()
                drop = library.Drop()

                from_net >> filter >> SavePkt() >> aggregate
                aggregate.up >> update
                aggregate.other >> get_pkt

                for i in range(n_workers):
                    net_alloc = net.NetAlloc()
                    update >> net_alloc >> Copy(configure=[i]) >> to_net  # send to dikdik
                    net_alloc.oom >> drop


                from_net.nothing >> drop
                filter.other >> net_free
                update >> get_pkt
                get_pkt >> net_free

        if nic == 'dpdk':
            nic_rx('nic_rx', process='dpdk', cores=range(1))
        else:
            nic_rx('nic_rx', device=target.CAVIUM, cores=range(12))
            


c = Compiler(main)
c.include = r'''
#include "protocol_binary.h"
''' + define + addr
c.testing = 'while (1) pause();'
if nic == 'dpdk':
    c.generate_code_and_run()
else:
    c.generate_code_as_header()
    c.generate_code_and_compile()


