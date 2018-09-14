from dsl import *
from compiler import Compiler
import target, queue, net, library

MAX_ELEMS = 64
n_cores = 1

Enq, Deq, DeqRelease = \
    queue.queue_custom("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task",
                       enq_blocking=True, enq_atomic=True, deq_atomic=True, enq_output=True)

class MakeTuple(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output("struct tuple*", Int)

    def impl(self):
        self.run_c(r'''
  static uint32_t count = 1;
  struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));

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
    output { out(t, 0); }
        ''')

class Scheduler(Element):
    def configure(self):
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
    output { out(0); }
        ''')

class Display(Element):
    def configure(self):
        self.inp = Input(queue.q_buffer)
        self.out = Output(queue.q_buffer)

    def impl(self):
        self.run_c(r'''
    (q_buffer buff) = inp();

    static uint32_t last = 0;
    if(buff.entry) {
        struct tuple* t = (struct tuple*) buff.entry;

        uint32_t task = htonl(t->task & 0xffffff00);
        uint32_t id = htonl(t->id);
        uint32_t data = htonl(t->data[87]);
        //if(task % 100000 == 0)
        printf("t: %d\n", task);
        if(task != data)
          printf("task = %d, data = %d\n", task, data);
        assert(task == data);
        if(id != task-1)
          printf("task = %d, id = %d\n", task, id);
        assert(id == task-1);
#if 1
        uint32_t this = task;
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
        self.inp = Input(SizeT, 'void*', 'void*')
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
        (size_t size, void* pkt, void* buf) = inp();
        output { out(pkt, buf); }
        ''')


class nic_rx(Segment):
    def impl(self):
        from_net = net.FromNet()
        from_net_free = net.FromNetFree()
        enq = Enq()
        make_tuple = MakeTuple()
        free = Free()

        from_net.nothing >> library.Drop()

        from_net >> make_tuple >> enq >> free
        from_net >> DropSize() >> from_net_free

        run_order(enq, from_net_free)


class run(Segment):
    def impl(self):
        Scheduler() >> Deq() >> Display() >> DeqRelease()


#nic_rx('nic_rx', device=target.CAVIUM, cores=range(4))
nic_rx('nic_rx', process='test_queue')
run('run', process='app', cores=range(1))

c = Compiler()
c.include_h = r'''
struct tuple {
  uint32_t data[88];
  uint32_t id;
  uint8_t task;
  uint8_t pad[3];
} __attribute__ ((packed));

'''
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
