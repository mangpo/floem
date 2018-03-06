from floem import *
import cache_smart, library


class Mult2(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        state->val = state->key * 2;
        output { out(); }
        ''')

class SaveKey(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        state->key = x;
        output { out(); }
        ''')


class SaveKV(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        (int x, int y) = inp();
        state->key = x;
        state->val = y;
        output { out(); }
        ''')

class OnlyVal(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        int val = state->val;
        output { out(val); }
        ''')

# CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd = \
#     cache_smart.smart_cache('MyCache', Int, [Int], write_policy=Cache.write_back, write_miss=Cache.write_alloc, set_return_value=True)


CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, CacheState = \
    cache_smart.smart_cache_with_state('MyCache', (Int, 'key'), [(Int, 'val')],
                           var_size=False, hash_value=False,
                           write_policy=Cache.write_back, write_miss=Cache.write_alloc)


class MyState(CacheState):
    key = Field(Int)
    val = Field(Int)


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class compute(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.inp >> SaveKey() >> CacheGetStart() >> Mult2() >> CacheGetEnd() >> OnlyVal() >> self.out

        class set(CallablePipeline):
            def configure(self):
                self.inp = Input(Int, Int)

            def impl(self):
                self.inp >> SaveKV() >> CacheSetStart() >> CacheSetEnd() >> library.Drop()

        compute('compute')
        set('set')


c = Compiler(main)
c.testing = r'''
set(1, 100);
out(compute(11)); out(compute(1)); out(compute(11)); out(compute(1)); 
set(11, 222); out(compute(11)); out(compute(1));
'''
c.generate_code_and_run([22,100,22,100, 222, 100])