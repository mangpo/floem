from dsl2 import *
import queue_smart2
from compiler import Compiler

class MyState(State):
    core = Field(Int)
    keylen = Field(Int)
    key = Field(Pointer(Uint(8)), copysize='state.keylen')
    p = Field(Pointer(Int), shared='data_region')

class main(Pipeline):
    state = PerPacket(MyState)

    class Save(Element):
        def configure(self):
            self.inp = Input(Int, Uint(8))
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    (int len, uint8_t data) = inp();
    state.core = 0;
    state.key = (uint8_t *) malloc(len);
    state.keylen = len;
    int i;
    for(i=0; i<len ; i++)
        state.key[i] = data;

    int* p = data_region;
    p[data] = 100 + data;
    state.p = &p[data];
    output { out(); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d %d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1], *state.p);
            fflush(stdout);
            ''')

        def impl_cavium(self):
            self.run_c(r'''
            int* x;
            dma_read((uintptr_t) state.p, sizeof(int), (void**) &x);
            printf("%d %d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1], nic_htonl(*x));
            fflush(stdout);
            dma_free(x);
            ''')

    class DisplayClean(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("clean: %d %d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1], *state.p);
            fflush(stdout);
            ''')

    Enq, Deq, Scan = queue_smart2.smart_queue("queue", 16, 2, 1, enq_blocking=True, clean=True)

    class push(API):
        def configure(self):
            self.inp = Input(Int, Uint(8))

        def impl(self):
            self.inp >> main.Save() >> main.Enq()

            main.Scan() >> main.DisplayClean()

    class pop(InternalLoop):
        # def configure(self):
        #     self.inp = Input(Size)

        def impl(self):
            self.core_id >> main.Deq() >> main.Display()

    def impl(self):
        MemoryRegion("data_region", 4 * 100)
        main.push('push', process="varsize_deq")
        main.pop('pop', device=target.CAVIUM) # process="queue_shared_data2")

master_process("varsize_deq")

c = Compiler(main)
c.testing = r'''
int i;
for(i=0; i<64; i++) {
  push(i,i);
}
'''
c.generate_code_as_header()
c.compile_and_run("cavium_varsize_deq_test")