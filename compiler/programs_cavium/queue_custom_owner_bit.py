from dsl2 import *
from compiler import Compiler
import target, queue2, net_real, library_dsl2

MAX_ELEMS = 64
n_cores = 1

Enq, Deq, DeqRelease = \
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task",
                                  enq_blocking=True, enq_atomic=True, enq_output=True,
                                  deq_atomic=True)

class MakeTuple(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    static int count = 0;
    struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));
    t->id = count;
    t->task = 1;

    for(int i=0; i<248; i++) t->data[i] = count;
    __sync_fetch_and_add(&count, 1);
    output { out(t, 0); }

  uint32_t old, new;
  size_t loop = 0;
  do{
    __SYNC;
    old = count;
    new = old + 1;
    //if(new > 999) new = 1;                                                                          
    loop++;
    if(loop % 1000 == 0) printf("id stuck: count = %ld\n", loop);
    if(loop >= 1000) {
      set_health(12);
    }

    assert(loop < 1000);
  } while(!__sync_bool_compare_and_swap32(&count, old, new));

  t->id = old-1;
  t->task = old;

  int i;
  for(i=0; i<88; i++) t->data[i] = old;
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

    static uint32_t last = 0;
    if(buff.entry) {
        struct tuple* t = (struct tuple*) buff.entry;

        uint32_t task = htonl(t->task);
        uint32_t id = htonl(t->id);
        if(task % 100000 == 0) printf("t: %d\n", task);
        if(t->task != t->data[87])
          printf("task = %d, data = %d\n", task, htonl(t->data[87]));
        assert(t->task == t->data[87]);
        if(id != task-1)
          printf("task = %d, id = %d\n", task, id);
        assert(id == task-1);
#if 1
        uint32_t this = htonl(t->task);
        __SYNC;
        if(this > last) {
          if(!((this <= last + 40) || (last + (999 - this) <= 40)))
            printf("this = %d, last = %d\n", this, last);
          assert((this <= last + 40) || (last + (999 - this) <= 40));
        } else {
          if(!((last <= this + 40) || (this + (999 - last) <= 40)))
            printf("this = %d, last = %d\n", this, last);
          assert((last <= this + 40) || (this + (999 - last) <= 40));
        }
        if(this > last) {
          last = this;
          __SYNC;
        }
#endif

#if 0
        assert(task == last+1);
        last = task;
#endif
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
run('run', process='app', cores=range(1))

c = Compiler()
c.include_h = r'''
struct tuple {
  uint32_t data[88];
  uint32_t id;
  uint32_t task;
} __attribute__ ((packed));

'''
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
