import queue
from dsl import*
from compiler import Compiler

n_cores = 4

class Entry(State):
    flag = Field(Uint(8))
    task = Field(Uint(8))
    len = Field(Uint(16))
    checksum = Field(Uint(8))
    pad = Field(Uint(8))
    val = Field(Int)
    layout = [flag, task, len, checksum, pad, val]

EnqAlloc, EnqSubmit, DeqGet, DeqRelease, clean = \
    queue.queue_default("queue", 32, 3, n_cores, enq_atomic=True, deq_atomic=True, clean=True)

class ComputeCore(Element):
    def configure(self):
        self.inp = Input(Int, SizeT)  # val, core
        self.out_size_core = Output(SizeT, SizeT)  # size, core
        self.out_val = Output(Int)

    def impl(self):
        self.run_c(r'''
        (int x, size_t core) = inp();
        output { out_val(x); out_size_core(4, core); }
        ''')

class FillEntry(Element):
    def configure(self):
        self.in_entry = Input(queue.q_buffer)
        self.in_val = Input(Int)
        self.out = Output(queue.q_buffer)

    def impl(self):
        self.run_c(r'''
    (q_buffer buff) = in_entry();
    Entry* e = (Entry*) buff.entry;
    int v = in_val();
    if(e != NULL) {
      e->val = v;
      printf("%d enq\n", v);
      }
    output switch { case (e != NULL): out(buff); }
        ''')


class CleanPrint(Element):
    def configure(self):
        self.inp = Input(queue.q_buffer)

    def impl(self):
        self.run_c(r'''
    (q_buffer buff) = inp();
    Entry* e = (Entry*) buff.entry;
    if(e->val) printf("%d clean\n", e->val);
        ''')


class rx_write(CallablePipeline):
    def configure(self):
        self.inp  = Input(Int, SizeT)  # val, core

    def impl(self):
        compute_core = ComputeCore()
        fill_entry = FillEntry()
        self.inp >> compute_core
        compute_core.out_size_core >> EnqAlloc() >> fill_entry.in_entry
        compute_core.out_val >> fill_entry.in_val
        fill_entry >> EnqSubmit()

        clean >> CleanPrint()

class rx_read(CallablePipeline):
    def configure(self):
        self.inp = Input(SizeT)
        self.out = Output(queue.q_buffer)

    def impl(self):
        self.inp >> DeqGet() >> self.out

class rx_release(CallablePipeline):
    def configure(self):
        self.inp = Input(queue.q_buffer)

    def impl(self):
        self.inp >> DeqRelease()

Entry(instance=False)
rx_write('rx_write')
rx_read('rx_read')
rx_release('rx_release')

c = Compiler()
c.testing = r'''
Entry* e;
q_buffer buff;
rx_write(1,1);
rx_write(2,2);
rx_write(5,1);

buff = rx_read(1);
e = (Entry*) buff.entry;
out(e->val);
rx_release(buff);

buff = rx_read(1);
e = (Entry*) buff.entry;
out(e->val);
rx_release(buff);

buff = rx_read(2);
e = (Entry*) buff.entry;
out(e->val);
rx_release(buff);

buff = rx_read(2);
e = (Entry*) buff.entry;
out(e);


rx_write(11,1);
rx_write(12,1);
rx_write(13,1);
rx_write(14,1);
buff = rx_read(1);
e = (Entry*) buff.entry;
out(e->val);
rx_release(buff);
rx_write(14,1);

'''

c.generate_code_and_run([1,"enq",2,"enq", 5, "enq", 1, 5, 2, 0, 11, "enq", 1, "clean", 5, "clean",  12, "enq", 13, "enq", 11, 11, "clean", 14, "enq"])
#c.generate_code_and_run([1,"enq",2,"enq", 5, "enq", 1, 5, 2, 0, 1, "clean", 5, "clean", 11, "enq",  12, "enq", 13, "enq", 11, 11, "clean", 14, "enq"])