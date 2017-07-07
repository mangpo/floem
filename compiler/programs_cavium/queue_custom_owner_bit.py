from dsl2 import *
from compiler import Compiler
import target, queue2

MAX_ELEMS = 30
n_cores = 1

Enq, Deq, DeqRelease, Scan, ScanRelease = \
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task",
                                  blocking=True, enq_atomic=True, enq_output=True)

Inject = create_inject("inject", "struct tuple*", 100, "random_count", 100000)

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
        self.inp = Input("struct tuple*", "uintptr_t")
        self.out = Output("struct tuple*", "uintptr_t")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t, uintptr_t p) = inp();
    printf("t: %d %d\n", t->task, t->id);
    output { out(t, p); }
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
        Inject() >> GetCore() >> Enq() >> Free()


class run(InternalLoop):
    def impl(self):
        Scheduler() >> Deq() >> Display() >> DeqRelease()


nic_rx('nic_rx', device=target.CAVIUM, cores=range(4))
#nic_rx('nic_rx', process='test_queue')
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

# TODO
# 1. test atomic
# 5. one nic thread per out queue