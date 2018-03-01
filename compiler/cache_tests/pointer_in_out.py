from floem import *
import cache_smart, library


class Mult2(Element):
    def configure(self, *params):
        self.inp = Input(Pointer(Int), Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int* key, int keylen) = inp();
        int x = *key;
        int y = 2*x;
        output { out(key, keylen, sizeof(int), &y); }
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
        output { out(&x, sizeof(int)); }
        ''')

class KV2Pointer(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int x, int y) = inp();
        output { out(&x, sizeof(int), sizeof(int), &y); }
        ''')

CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd = \
    cache_smart.smart_cache('MyCache', Pointer(Int), [Pointer(Int)],
                            var_size=True, set_return_value=True,
                            write_policy=Cache.write_back, write_miss=Cache.write_alloc)


class MyState(cache_smart.CacheState):
    pass


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class compute(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.inp >> Key2Pointer() >> CacheGetStart() >> Mult2() >> CacheGetEnd() >> OnlyVal() >> self.out

        class set(CallablePipeline):
            def configure(self):
                self.inp = Input(Int, Int)

            def impl(self):
                self.inp >> KV2Pointer() >> CacheSetStart() >> CacheSetEnd() >> library.Drop()

        compute('compute')
        set('set')


c = Compiler(main)
c.testing = r'''
set(1, 100);
out(compute(11)); out(compute(1)); out(compute(11)); out(compute(1)); 
set(11, 222); out(compute(11)); out(compute(1));
'''
c.generate_code_and_run([22,100,22,100, 222, 100])