from dsl2 import *
from compiler import Compiler
import target, queue2, net_real, library_dsl2

MAX_ELEMS = 30
n_cores = 1

Enq, Deq, DeqRelease = \
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task",
                                  enq_blocking=False, enq_atomic=True, enq_output=True)

class MakeTuple(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    static int count = 0;
    struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));
    t->id = count;
    t->task = count;
    __sync_fetch_and_add(&count, 1);
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
        self.inp = Input(queue2.q_buffer)
        self.out = Output(queue2.q_buffer)

    def impl(self):
        self.run_c(r'''
    (q_buffer buff) = inp();
    if(buff.entry) {
        printf("t: %d %d\n", buff.entry->task, buff.entry->id);
    }
    output { out(buff); }
        ''')

class Free(Element):
    def configure(self):
        self.inp = Input("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();
    free(t);
        ''')

class DropSize(Element):
    def configure(self):
        self.inp = Input(Size, 'void*', 'void*')
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
        (size_t size, void* pkt, void* buf) = inp();
        output { out(pkt, buf); }
        ''')


class nic_rx(InternalLoop):
    def impl(self):
        from_net = net_real.FromNet()
        from_net_free = net_real.FromNetFree()
        enq = Enq()
        make_tuple = MakeTuple()
        free = Free()

        from_net.nothing >> library_dsl2.Drop()

        from_net >> make_tuple >> enq >> free
        from_net >> DropSize() >> from_net_free

        run_order(enq, from_net_free)


class run(InternalLoop):
    def impl(self):
        Scheduler() >> Deq() >> Display() >> DeqRelease()


nic_rx('nic_rx', device=target.CAVIUM, cores=range(4))
#nic_rx('nic_rx', process='test_queue')
run('run', process='app')

c = Compiler()
c.include_h = r'''
struct tuple {
  int		task, id;
};
'''
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")