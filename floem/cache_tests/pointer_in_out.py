from floem import *

class Storage(State):
    mem = Field(Array(Int, 100))

    def init(self):
        self.mem = lambda x: 'init_mem(%s, 100)' % x

class Mult2(Element):
    this = Persistent(Storage)

    def configure(self):
        self.inp = Input(Pointer(Int), Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def states(self, storage):
        self.this = storage

    def impl(self):
        self.run_c(r'''
        (int* key, int keylen) = inp();
        
        int x = *key;
        int y = this->mem[x];
        
        if(y == -1) {
            y = 2*x;
            this->mem[x] = y;
        }
        
        output { out(key, keylen, sizeof(int), &y); }
        ''')

class LookUp(Element):
    this = Persistent(Storage)

    def configure(self):
        self.inp = Input(Pointer(Int), Int, Int, Pointer(Int))
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def states(self, storage):
        self.this = storage

    def impl(self):
        self.run_c(r'''
        (int* key, int keylen, int vallen, int* val) = inp();
        
        int x = *key;
        int y = *val;
        this->mem[x] = y;
        
#ifdef DEBUG
        printf("update storage\n");
#endif

        output { out(key, keylen, vallen, val); }
        ''')

class OnlyVal(Element):
    def configure(self):
        self.inp = Input(Pointer(Int), Int, Int, Pointer(Int))
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        (int* key, int keylen, int vallen, int* val) = inp();
        output { out(*val); }
        ''')

class Key2Pointer(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Pointer(Int), Int)

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        state->hash = 0;
        output { out(&x, sizeof(int)); }
        ''')

class KV2Pointer(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int x, int y) = inp();
        state->hash = 0;
        output { out(&x, sizeof(int), sizeof(int), &y); }
        ''')


class Display(Element):
    def configure(self):
        self.inp = Input(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int* key, int keylen, int vallen, int* val) = inp();
        int x = *key;
        printf("conf%d\n", x);
        ''')


CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, \
CacheState, Key2State, KV2State, State2Key, State2KV = \
    cache_smart.smart_cache('MyCache', Pointer(Int), [Pointer(Int)],
                            var_size=True, hash_value=True,
                            write_policy=Cache.write_back, write_miss=Cache.write_alloc)


class MyState(CacheState):
    pass


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        storage = Storage()

        class compute(CallableSegment):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.inp >> Key2Pointer() >> CacheGetStart() >> Mult2(states=[storage]) >> CacheGetEnd() >> OnlyVal() >> self.out

        class set(CallableSegment):
            def configure(self):
                self.inp = Input(Int, Int)

            def impl(self):
                self.inp >> KV2Pointer() >> CacheSetStart() >> LookUp(states=[storage]) >> CacheSetEnd() >> Display()

        compute('compute')
        set('set')


c = Compiler(main)
c.include = r'''
void init_mem(int* mem, int n) {
    int i;
    for(i=0; i<n; i++)
        mem[i] = -1;
}
'''
c.testing = r'''
set(1, 100);
out(compute(11)); out(compute(1)); out(compute(11)); out(compute(1)); 
set(11, 222); out(compute(11)); out(compute(1));
'''
c.generate_code_and_run(['conf1',22,100,22,100,
                         'conf11', 222, 100])