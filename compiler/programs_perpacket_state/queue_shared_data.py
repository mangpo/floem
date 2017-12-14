from dsl import *
import queue_smart
from compiler import Compiler

class MyState(State):
    core = Field(Int)
    keylen = Field(Int)
    key = Field(Pointer(Uint(8)), size='state->keylen')
    p = Field(Pointer(Int), shared='data_region')


class main(Flow):
    state = PerPacket(MyState)

    class Save(Element):
        def configure(self):
            self.inp = Input(Int, Uint(8))
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    (int len, uint8_t data) = inp();
    state->core = 0;
    state->key = (uint8_t *) malloc(len);
    state->keylen = len;
    for(int i=0; i<len ; i++)
        state.key[i] = data;
    int* p = data_region;
    p[data] = 100 + data;
    state->p = &p[data];
    output { out(); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d %d %d %d\n", state->keylen, state->key[0], state->key[state.keylen-1], *state->p);
            fflush(stdout);
            ''')

    Enq, Deq, Scan = queue_smart.smart_queue("queue", 32, 128, 2, 1)

    class push(CallablePipeline):
        def configure(self):
            self.inp = Input(Int, Uint(8))

        def impl(self):
            self.inp >> main.Save() >> main.Enq()

    class pop(Pipeline):
        # def configure(self):
        #     self.inp = Input(Size)

        def impl(self):
            self.core_id >> main.Deq() >> main.Display()

    def impl(self):
        MemoryRegion("data_region", 4 * 100)
        main.push('push', process="queue_shared_data1")
        main.pop('pop', process="queue_shared_data2")

master_process("queue_shared_data1")

c = Compiler(main)
c.generate_code_as_header()
c.depend = {"queue_shared_data1_main": ['queue_shared_data1'],
            "queue_shared_data2_main": ['queue_shared_data2']}
c.compile_and_run(["queue_shared_data1_main", "queue_shared_data2_main"])