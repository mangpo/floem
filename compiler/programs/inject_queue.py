from dsl import *
from elements_library import *
from queue import *

Inc = create_add1("Inc", "int")
Inject = create_inject("Inject", "int", 8, "gen_func")
enq, deq = create_circular_queue_instances("queue", "int", 4)

inject = Inject()
inc1 = Inc()
inc2 = Inc()

@internal_trigger("t")
def enqueue():
    enq(inc1(inject()))

@API("dequeue", -1)
def dequeue():
    return inc2(deq())

c = Compiler()
c.include = r'''int gen_func(int i) { return i; }'''
c.testing = r'''
usleep(10000);
for(int i=0; i<8; i++) {
    printf("%d\n", dequeue());
    usleep(50);
}
out(dequeue());
'''
c.generate_code_and_run() #range(2,10) + [-1])
