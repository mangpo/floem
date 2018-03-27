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
''' % (n_params, n_groups, buffer_size)

class param_message(State):
    group_id = Field(Int)
    member_id = Field(Uint(8))
    start_id = Field(Uint(64))
    n = Field(Int)
    parameters = Field(Array(Int))

class param_aggregate(State):
    group_id = Field(Int)
    start_id = Field(Uint(64))
    n = Field(Int)
    bitmap = Field(Uint(8))
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

class FindGroup(Element):
    buffer = Persistent(param_buffer)

    def configure(self):
        self.inp = Input("void*")
        self.out = Output()
        self.buffer = param_buffer_inst

    def impl(self):
        self.run_c(r'''
(void* pkt) = inp();
udp_message* udp_msg = pkt;
param_message* param_msg = udp_msg->payload;

int group_id = param_msg->group_id;
int key = group_id % BUFFER_SIZE;
param_aggregate* agg = &buffer->groups[key];
bool pass;
uint8_t bit;
int i;

spinlock_lock(&agg->lock);
if(agg->group_id == -1 || agg->group_id == group_id) {
    if(agg->group_id == -1) agg->group_id = group_id;
    bit = 1 << param_msg->member_id;
    if(bit & agg->bitmap == 0 && agg->n == param_msg->n) {
        pass = true;
        agg->bitmap &= bit;
        for(i=0; i<param_msg->n; i++) {
            agg->parameters[i] += param_msg->parameters[i];
        }
    }
    else {
        pass = false;
        printf("Fail: group_id = %d, bitmap = %d, bit = %d, n = %d, %d\n", group_id, agg->bitmap, bit, agg->n, param_msg->n);
        assert(0);
    }
    
}
else {
    pass = false;
    printf("Fail: group_id = %d = %d\n", group_id, agg->group_id);
    assert(0);
}
spinlock_unlock(&agg->lock);

output {
    out();
}
        ''')

class Aggregate(Element):
    def configure(self):
        self.inp = Input("param_message*", "param_aggregate*")
        self.out = Output("void*")


    def impl(self):
        self.run_c(r'''
(param_message* param_msg, param_aggregate* agg) = inp();
1 << param_msg->member_id
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
    output { out(pkt); }
                ''')

class nic_rx(Pipeline):
    def impl(self):
        from_net = net.FromNet()
        to_net = net.ToNet()
        net_free = net.FromNetFree()

        from_net >> Filter() >> SaveState()