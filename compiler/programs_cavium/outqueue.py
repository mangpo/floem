from dsl2 import *
from compiler import Compiler
import queue2

MAX_ELEMS = 10
n_cores = 4

class Tuple(State):
    task = Field(Int)
    id = Field(Int)

    def init(self):
        self.declare = False

Inject = create_inject("inject", Pointer(Tuple), 100, "random_count", 100000)

Enq, Deq, DeqRelease, Scan, ScanRelease = \
    queue2.queue_custom_owner_bit("tx_queue", Tuple, MAX_ELEMS, n_cores, "task", blocking=False)

class GetCore(Element):
    def configure(self):
        self.inp = Input(Pointer(Tuple))
        self.out = Output(Pointer(Tuple), Size)

    def impl(self):
        self.run_c(r'''
        (Tuple* t) = inp();
        output { out(t, t->id %s %s); }
        ''' % ('%', n_cores))

class Display(Element):
    def configure(self):
        self.inp = Input(Pointer(Tuple), 'uintptr_t')
        self.out = Output(Pointer(Tuple), 'uintptr_t')

    def impl(self):
        self.run_c(r'''
        (Tuple* t, uintptr_t addr) = inp();
        if(t) printf("t: id = %d\n", t->id);
        output switch { case t: out(t, addr); }
        ''')

class app(InternalLoop):
    def impl(self):
        Inject() >> GetCore() >> Enq()

class nic(InternalLoop):
    def impl(self):
        self.core_id >> Deq() >> Display() >> DeqRelease()

app('app')
nic('nic', cores=[0,1,2,3])

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>

typedef struct _Tuple { int task;
int id;
 } Tuple;

Tuple* random_count(size_t i) {
  Tuple* t = (Tuple*) malloc(sizeof(Tuple));
  t->task = 10;
  t->id = i;
  return t;
}
'''
c.testing = r'''
while(1);
'''
c.generate_code_and_run()
#c.generate_code_as_header()