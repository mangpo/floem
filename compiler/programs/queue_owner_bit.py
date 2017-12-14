from dsl import *
import queue
from compiler import Compiler

n_cores = 2


class Tuple(State):
    val = Field(Int)
    task = Field(Uint(8))
    layout = [val, task]

class Display(Element):
    def configure(self):
        self.inp = Input(queue.q_buffer)
        self.out = Output(queue.q_buffer)

    def impl(self):
        self.run_c(r'''
        q_buffer buff = inp();
        Tuple* t = (Tuple*) buff.entry;
        if(t) printf("%d\n", t->val);
        output switch { case t: out(buff); }
        ''')

Enq, Deq, Release = queue.queue_custom('queue', Tuple, 4, n_cores, Tuple.task)

class RxWrite(CallablePipeline):
    def configure(self):
        self.inp = Input(Pointer(Tuple), SizeT)

    def impl(self):
        enq = Enq()
        self.inp >> enq


class RxPrint(CallablePipeline):
    def configure(self):
        self.inp = Input(SizeT)

    def impl(self):
        deq = Deq()
        release = Release()
        display = Display()
        self.inp >> deq >> display >> release

RxWrite('mysend')
RxPrint('process')

c = Compiler()
c.testing = r'''
Tuple tuples[10];
for(int i=0; i<10;i++) {
    tuples[i].task = 10;
    tuples[i].val = i;
}

for(int i=0; i<10;i++) {
    mysend(&tuples[i], 0);
    process(0);
}

for(int i=0; i<10;i++) {
    tuples[i].val = 100 + i;
    mysend(&tuples[i], 1);
    tuples[i].task = 0;
}

for(int i=0; i<10;i++) {
    process(1);
}
'''
c.generate_code_and_run(range(10) + [100, 101, 102, 103])