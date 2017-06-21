from dsl2 import *
import queue2
from compiler import Compiler

n_cores = 2


class Tuple(State):
    task = Field(Int)
    val = Field(Int)


class Display(Element):
    def configure(self):
        self.inp = Input(Pointer(Tuple))
        self.out = Output(Pointer(Tuple))

    def impl(self):
        self.run_c(r'''
        (Tuple* t) = inp();
        if(t) printf("%d\n", t->val);
        output switch { case t: out(t); }
        ''')

Enq, Deq, Release, Scan = queue2.queue_custom_owner_bit('queue', Tuple, 4, n_cores, Tuple.task,
                                                  blocking=False, enq_atomic=False)


class RxWrite(API):
    def configure(self):
        self.inp = Input(Pointer(Tuple), Size)

    def impl(self):
        enq = Enq()
        self.inp >> enq


class RxPrint(API):
    def configure(self):
        self.inp = Input(Size)

    def impl(self):
        deq = Deq()
        release = Release()
        display = Display()
        self.inp >> deq >> display >> release

RxWrite('send')
RxPrint('process')

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
'''
c.testing = r'''
Tuple tuples[10];
for(int i=0; i<10;i++) {
    tuples[i].task = 10;
    tuples[i].val = i;
}

for(int i=0; i<10;i++) {
    send(&tuples[i], 0);
    process(0);
}

for(int i=0; i<10;i++) {
    tuples[i].val = 100 + i;
    send(&tuples[i], 1);
    tuples[i].task = 0;
}

for(int i=0; i<10;i++) {
    process(1);
}
'''
c.generate_code_and_run(range(10) + [100, 101, 102, 103])