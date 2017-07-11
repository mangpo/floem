from dsl2 import *
import queue_smart2, net_real
from compiler import Compiler

class MyState(State):
    core = Field(Int)
    keylen = Field(Int)
    key = Field(Pointer(Uint(8)), copysize='state.keylen')

class Count(State):
    count = Field(Int)
    def init(self):
        self.count = 0

class main(Pipeline):
    state = PerPacket(MyState)

    class Save(Element):
        this = Persistent(Count)

        def configure(self):
            self.inp = Input('void*', 'void*')
            self.out = Output()
            self.this = Count()

        def impl(self):
            self.run_c(r'''
    inp();
    this->count++;
    state.core = 0;
    state.key = (uint8_t *) malloc(this->count);
    state.keylen = this->count;
    for(int i=0; i<this->count ; i++)
        state.key[i] = this->count;
    output { out(); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1]);
            fflush(stdout);
            ''')

        def impl_cavium(self):
            self.run_c(r'''
  int keylen = my_htonl(_state->entry->keylen);
  printf("%d %d %d\n", keylen, _state->key[0],  _state->key[keylen-1]);
  fflush(stdout);
            ''')

    Enq, Deq, Scan = queue_smart2.smart_queue("queue", 256, 2, 1)

    class push(InternalLoop):
        def impl(self):
            from_net = net_real.FromNet()
            from_net_free = net_real.FromNetFree()

            from_net >> main.Save() >> main.Enq()
            from_net >> from_net_free

    class pop(InternalLoop):
        # def configure(self):
        #     self.inp = Input(Size)

        def impl(self):
            self.core_id >> main.Deq() >> main.Display()

    def impl(self):
        main.push('push', device=target.CAVIUM) #process="queue_shared_data1")
        main.pop('pop', process="queue_shared_data2")

#master_process("queue_shared_data1")
master_process("queue_shared_data2")

c = Compiler(main)
c.include = r'''
#include <rte_memcpy.h>
#include "../queue.h"
#include "../shm.h"
'''

c.generate_code_as_header()
c.depend = {"queue_shared_data1_main": ['queue_shared_data1'],
            "queue_shared_data2_main": ['queue_shared_data2']}
c.compile_and_run(["queue_shared_data1_main", "queue_shared_data2_main"])