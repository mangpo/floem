import queue
from dsl import *

n_cores = 4

enq, deq, adv = queue.create_copy_queue_many2many_batch_instances("queue", "int", 4, n_cores)

@API("enqueue")
def enqueue(input):
    enq(input)

@API("peak", default_return="NULL")
def peak(core_i):
    return deq(core_i)

@API("advance")
def advance(core_i):
    adv(core_i)

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
'''
c.testing = r'''
int x = 100;
enqueue(&x, 0);
x = 200;
enqueue(&x, 1);

out(*peak(0,0));
out(*peak(0,0));
out(*peak(1,0));
advance(0,1);
advance(1,1);

out(peak(0,0));
out(peak(1,0));

x = 301;
enqueue(&x, 2);
x = 302;
enqueue(&x, 2);
x = 303;
enqueue(&x, 2);

out(*peak(2,0));
out(*peak(2,1));
out(*peak(2,2));
out(peak(2,3));

advance(2,2);
out(*peak(2,0));
'''

c.generate_code_and_run([100,100,200,0,0,301,302,303,0,303])