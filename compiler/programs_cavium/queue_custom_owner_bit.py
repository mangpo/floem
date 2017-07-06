from dsl2 import *
from compiler import Compiler
import target, queue2

MAX_ELEMS = 8
n_cores = 1

rx_enq_creator, rx_deq_creator, rx_release_creator, scan = \
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task", blocking=True,
                                  enq_output=True)

Inject = create_inject("inject", "struct tuple*", 16, "random_count", 1000000)

class GetCore(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    output { out(t, 0); }
        ''')

class Scheduler(Element):
    def configure(self):
        self.out = Output(Size)

    def impl(self):
        self.run_c(r'''
    output { out(0); }
        ''')

class Display(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();
    printf("t: %d %d\n", t->task, t->id);
    output { out(t); }
        ''')

class Free(Element):
    def configure(self):
        self.inp = Input("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();
    free(t);
        ''')



class nic_rx(InternalLoop):
    def impl(self):
        Inject() >> GetCore() >> rx_enq_creator() >> Free()


class run(InternalLoop):
    def impl(self):
        Scheduler() >> rx_deq_creator() >> Display() >> rx_release_creator()


nic_rx('nic_rx', device=target.CAVIUM, cores=[0])
run('run', process='test_queue')

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>

struct tuple {
  int		task, id;
};

struct tuple* random_count(size_t i) {
  struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));
  t->task = 10;
  t->id = i;
  return t;
}
'''
c.testing = r'''
sleep(10);
'''
c.generate_code_as_header("test_queue")
#c.generate_code_and_run()