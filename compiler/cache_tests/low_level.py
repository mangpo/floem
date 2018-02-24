from floem import *
import cache, library

class Mult2(Element):
    def configure(self, *params):
        self.inp = Input(Int)
        self.out = Output(Int, Int)

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        output { out(x, 2*x); }
        ''')

class OnlyVal(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        (int key, int val) = inp();
        output { out(val); }
        ''')

CacheGet,CacheSet,CacheRelease = cache.cache_default('MyCache', Int, [Int], hash_value=False, var_size=False)


class compute(CallablePipeline):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        cache_get = CacheGet()
        cache_set = CacheSet()
        only_val = OnlyVal()

        self.inp >> cache_get
        cache_get.hit >> only_val
        cache_get.miss >> Mult2() >> cache_set >> only_val
        only_val >> self.out

class set(CallablePipeline):
    def configure(self):
        self.inp = Input(Int, Int)

    def impl(self):
        self.inp >> CacheSet() >> library.Drop()

compute('compute')
set('set')


c = Compiler()
c.testing = "out(compute(11)); out(compute(1)); out(compute(11)); out(compute(1)); set(11, 222); out(compute(11)); out(compute(1));"
c.generate_code_and_run([22,2,22,2, 222, 2])