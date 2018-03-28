from floem import *
import net

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

class MyState(State):
    pkt_buff = Field('void*')
    pkt = Field('void*')
    parameters = Field('int*')
    n = Field(Int)
    group_id = Field(Int)

class param_message(State):
    group_id = Field(Int)
    member_id = Field(Uint(8))
    start_id = Field(Uint(64))
    n = Field(Int)
    parameters = Field(Array(Int))

class param_message_out(State):
    group_id = Field(Int)
    n = Field(Int)
    parameters = Field(Array(Int))

class param_aggregate(State):
    group_id = Field(Int)
    start_id = Field(Uint(64))
    n = Field(Int)
    bitmap = Field(Int)
    lock = Field('spinlock_t')
    parameters = Field(Array(Int, buffer_size))

class param_buffer(State):
    groups = Field(param_aggregate, n_groups)

    def init(self):
        pass # TODO: lock_init

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
param_message* param_msg = udp_msg->payload;

int group_id = param_msg->group_id;
int old_group_id = agg->group_id;
int key = group_id % BUFFER_SIZE;
param_aggregate* agg = &buffer->groups[key];
bool pass = true, update = false;
int bit, bitmap, new_bitmap;
int i;

if(old_group_id == -1) {
    if(__sync_bool_compare_and_swap32(&agg->group_id, old_group_id, group_id)) {
        agg->start_id = param_msg->start_id;
        agg->n = param_msg->n;
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

if(agg->n != param_msg->n) {
    pass = false;
}

if(pass) {
    do {
        bitmap = agg->bitmap;
        bit = 1 << param_msg->member_id;
        if(bit & bitmap == 0) {
            pass = false;
            break;
        }
        new_bitmap = agg->bitmap | bit;
    } while(!__sync_bool_compare_and_swap32(&agg->bitmap, bitmap, new_bitmap));
    
    if(pass) {
        for(i=0; i<param_msg->n; i++) {
            __sync_fetch_and_add32(&agg->parameters[i], param_msg->parameters[i]);
        }
        
        if(new_bitmap == BITMAP_FULL)
            update = true;
    }
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
        self.out = Output()
        self.buffer = param_buffer_inst
        self.store = param_store_inst


    def impl(self):
        self.run_c(r'''
(param_aggregate* agg) = inp();
int start_id = agg->start_id;

state->group_id = agg->group_id;
state->n = agg->n;
state->parameters = &store->parameters[start_id];

memcpy(&store->parameters[start_id], agg->parameters, agg->n * sizeof(int));

memset(agg->parameters, 0, agg->n * sizeof(int));
agg->bitmap = 0;
agg->group_id = -1;

int size = sizeof(udp_message) + sizeof(param_message_out) + agg->n * sizeof(int));

output {
    out(size);
}
        ''')


class Copy(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
memcpy(pkt, state->pkt, sizeof(udp_message));

// TODO: fill in pkt

// TODO: fill in MAC address

output { out(size, pkt, buff); }
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

uint8_t pkt_ptr = pkt;
bool discard = (pkt_ptr[IP_PROTOCOL_POS] != 0x11); // UDP only

output switch {
    case disgard: other(pkt, buff);
    else: out(size, pkt, buff);
}
        ''')


class SaveState(Element):
    def configure(self):
        self.inp = Input(SizeT, "void *", "void *")
        self.out = Output()

    def impl(self):
        self.run_c(r'''
    (size_t size, void* pkt, void* buff) = inp();
    state->pkt_buff = buff;
    state->pkt = pkt;
    output { out(pkt); }
                ''')

class nic_rx(Pipeline):
    def impl(self):
        from_net = net.FromNet()
        to_net = net.ToNet()
        net_free = net.FromNetFree()

        from_net >> Filter() >> SaveState()