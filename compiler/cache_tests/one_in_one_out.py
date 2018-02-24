from floem import *
import cache_smart


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

CacheGetStart, CacheGetEnd = cache_smart.smart_cache('MyCache', Int, [Int])

class compute(CallablePipeline):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        self.inp >> CacheGetStart() >> Mult2() >> CacheGetEnd() >> OnlyVal() >> self.out

compute('compute')


c = Compiler()
c.testing = "out(compute(11)); out(compute(0));"
c.generate_code_and_run([22,0])