from floem import *
import cache_smart, queue_smart

class Storage(State):
    mem = Field(Array(Int, 100))

    def init(self):
        self.mem = lambda x: 'init_mem(%s, 100)' % x

class Mult2(Element):
    this = Persistent(Storage)

    def configure(self):
        self.inp = Input()
        self.out = Output()

    def states(self, storage):
        self.this = storage

    def impl(self):
        self.run_c(r'''
        int x = *state->key;
        int y = this->mem[x];
        
        if (x == 0) {
            state->vallen = 0;
        } else if(y == -1) {
            y = 2*x;
            this->mem[x] = y;
            state->vallen = y;
            state->vallen = sizeof(int);
        } else {
            state->vallen = y;
            state->vallen = sizeof(int);
        }
        
        output { out(); }
        ''')

class Store(Element):
    this = Persistent(Storage)

    def configure(self):
        self.inp = Input()
        self.out = Output()

    def states(self, storage):
        self.this = storage

    def impl(self):
        self.run_c(r'''
        assert(state->keylen == sizeof(int));
        assert(state->vallen == sizeof(int));
        int x = *state->key;
        int y = *state->val;
        this->mem[x] = y;
        
#ifdef DEBUG
        printf("update storage %d %d\n", x, y);
#endif

        output { out(); }
        ''')

class OnlyVal(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        int y;
        if(state->vallen == 0) { 
            y = -1; 
        } else {
            y = *state->val;
        }
        output { out(); }
        ''')

class Key2Pointer(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        state->hash = 0;
        state->key = &x;
        state->keylen = sizeof(int);
        output { out(); }
        ''')

class KV2Pointer(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        (int x, int y) = inp();
        state->hash = 0;
        state->key = &x;
        state->keylen = sizeof(int);
        state->val = &y;
        state->vallen = sizeof(int);
        output { out(); }
        ''')

class DisplayGet(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''
        int y;
        int x = *state->key;
        assert(state->keylen == sizeof(int));
        if(state->vallen == 0) { 
            y = -1; 
        } else {
            assert(state->vallen == sizeof(int));
            y = *state->val;
        }
        printf("    GET%d VAL%d\n", x, y);
        ''')


class DisplaySet(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''
        assert(state->keylen == sizeof(int));
        printf("    SET%d\n", *state->key);
        ''')

n_queues = 1
class QID(ElementOneInOut):
    def impl(self):
        self.run_c(r'''
        state->qid = state->hash %s %s;
        printf("qid: key = %s\n", *state.key);
        output { out(); }
        ''' % ('%', n_queues, '%d'))

class DebugSet(ElementOneInOut):
    def impl(self):
        self.run_c(r'''
        printf("debug: key = %d\n", *state.key);
        output { out(); }
        ''')


# CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, \
# CacheState, Key2State, KV2State, State2Key, State2KV = \
#     cache_smart.smart_cache('MyCache', Pointer(Int), [Pointer(Int)],
#                             var_size=True, hash_value='hash',
#                             write_policy=Cache.write_back, write_miss=Cache.write_alloc)

CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, CacheState = \
    cache_smart.smart_cache_with_state('MyCache', (Pointer(Int),'key','keylen'), [(Pointer(Int),'val','vallen')],
                            var_size=True, hash_value='hash',
                            write_policy=Cache.write_back, write_miss=Cache.write_alloc)

InEnq, InDeq, InClean = queue_smart.smart_queue("inqueue", 32, 16, n_queues, 2)
OutEnq, OutDeq, OutClean = queue_smart.smart_queue("outqueue", 32, 16, n_queues, 2)

class MyState(CacheState):
    key = Field(Pointer(Int), size='state->keylen')
    val = Field(Pointer(Int), size='state->vallen')
    keylen = Field(Int)
    vallen = Field(Int)

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        storage = Storage()


        class compute(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                enq = InEnq()
                self.inp >> Key2Pointer() >> CacheGetStart() >> QID() >> enq.inp[0]

        class set(CallablePipeline):
            def configure(self):
                self.inp = Input(Int, Int)

            def impl(self):
                enq = InEnq()
                self.inp >> KV2Pointer() >> CacheSetStart() >> QID() >> enq.inp[1]

        class nic_tx(Pipeline):
            def impl(self):
                deq = OutDeq()

                self.core_id >> deq
                deq.out[0] >> CacheGetEnd() >> DisplayGet()
                deq.out[1] >> DebugSet() >> CacheSetEnd() >> DisplaySet()

        class server(Pipeline):
            def impl(self):
                deq = InDeq()
                enq = OutEnq()

                self.core_id >> deq
                deq.out[0] >> Mult2(states=[storage]) >> enq.inp[0]
                deq.out[1] >> Store(states=[storage]) >> enq.inp[1]

        compute('compute')
        set('set')
        nic_tx('nic_tx', cores=[0])
        server('server', cores=[0])


c = Compiler(main)
c.include = r'''
void init_mem(int* mem, int n) {
    int i;
    for(i=0; i<n; i++)
        mem[i] = -1;
}
'''
c.testing = r'''
//set(1, 100);
//compute(11); compute(1); 
//compute(11); compute(1); 
//set(11, 222); compute(11); compute(1);
compute(0);
sleep(1);
'''
c.generate_code_and_run()