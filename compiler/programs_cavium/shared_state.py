from dsl2 import *
import net_real

class Count(State):
    count = Field(Int)

    def init(self):
        self.count = 0

class Counter(Element):
    this = Persistent(Count)

    def states(self):
        self.this = Count()

    def configure(self):
        self.inp = Input('void*', 'void*')
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
    (void* p, void* buf) = inp();
    this->count++;
    output { out(p, buf); }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    (void* p, void* buf) = inp();
    this->count++;
    output { out(p, buf); }
        ''')

class NICRx(InternalLoop):
    def impl(self):
        net_real.FromNet >> Counter() >> net_real.FromNetFree()