from dsl2 import *
import queue_smart2
from compiler import Compiler



class MyState(State):
    core = Field(Int)
    index = Field(Int)
    p = Field(Pointer(Int), shared='data_region')  # TODO

class main(Pipeline):
    state = PerPacket(MyState)

    class Save(Element):
        def configure(self):
            self.inp = Input(Int)
            self.out = Output()

        def impl(self):
            self.run_c(r'''
    state.index = inp(); state.p = data_region; state.core = 0; output { out(); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d\n", state.p[state.index]); fflush(stdout);
            ''')

    Enq, Deq, Scan = queue_smart2.smart_queue("queue", 32, 128, 2, 1)


    class push(API):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            self.inp >> main.Save() >> main.Enq()

    class pop(API):
        def configure(self):
            self.inp = Input(Size)

        def impl(self):
            self.inp >> main.Deq() >> main.Display()

    def impl(self):
        MemoryRegion("data_region", 4 * 100)
        main.push('push', process="queue_shared_p1")
        main.pop('pop', process="queue_shared_p2")
        master_process("queue_shared_p1")


c = Compiler(main)
c.include = r'''
#include <rte_memcpy.h>
'''

c.generate_code_as_header()
c.depend = {"queue_shared_p1_main": ['queue_shared_p1'],
            "queue_shared_p2_main": ['queue_shared_p2']}
c.compile_and_run(["queue_shared_p1_main", "queue_shared_p2_main"])