from dsl import *
from compiler import Compiler
import queue

MAX_ELEMS = 10
n_cores = 4

class Tuple(State):
    task = Field(Uint(8))
    id = Field(Int)

    def init(self):
        self.declare = False

Inject = create_inject("inject", Pointer(Tuple), 100, "random_count", 100000)

Enq, Deq, DeqRelease = queue.queue_custom("tx_queue", Tuple, MAX_ELEMS, n_cores, "task")

class GetCore(Element):
    def configure(self):
        self.inp = Input(Pointer(Tuple))
        self.out = Output(Pointer(Tuple), SizeT)

    def impl(self):
        self.run_c(r'''
        (Tuple* t) = inp();
        output { out(t, t->id %s %s); }
        ''' % ('%', n_cores))

class Display(Element):
    def configure(self):
        self.inp = Input('q_buffer')
        self.out = Output('q_buffer')

    def impl(self):
        self.run_c(r'''
        (q_buffer buff) = inp();
        Tuple* t = buff.entry;
        if(t) printf("t: id = %d\n", t->id);
        output switch { case t: out(buff); }
        ''')

class app(Pipeline):
    def impl(self):
        Inject() >> GetCore() >> Enq()

class nic(Pipeline):
    def impl(self):
        self.core_id >> Deq() >> Display() >> DeqRelease()

app('app')
nic('nic', cores=[0,1,2,3])

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>

typedef struct _Tuple { 
  int id;
  uint8_t task;
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