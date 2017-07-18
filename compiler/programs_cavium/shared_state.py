from dsl2 import *
import net_real
import target
from compiler import Compiler

class Count(State):
    count = Field(Int)

    def init(self):
        self.count = 100

count = Count()

class Counter(Element):
    this = Persistent(Count)

    def states(self):
        self.this = count

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

    int *count;
    dma_read(this, sizeof(int), (void **) &count);

    int local = nic_htonl(*count);
    local++;
    *count = nic_ntohl(local);

    dma_write(this, sizeof(int), count);

    // Free the block
    dma_free(count);
    output { out(p, buf); }
        ''')

class ReadCounter(Element):
    this = Persistent(Count)

    def states(self):
        self.this = count

    def impl(self):
        self.run_c(r'''
    printf("count = %d\n", this->count);
        ''')


class NICRx(InternalLoop):
    def impl(self):
        net_real.FromNet() >> Counter() >> net_real.FromNetFree()


class GetCount(API):
    def impl(self):
        ReadCounter()


NICRx('nic_rx', device=target.CAVIUM, cores=[0,1,2,3])
GetCount('get_count', process='tmp')

master_process('tmp')

c = Compiler()
c.generate_code_as_header()