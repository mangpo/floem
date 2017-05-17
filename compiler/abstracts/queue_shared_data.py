from elements_library import *
import queue_smart

state = create_state("mystate", "int core; int keylen; uint8_t *key @copysize(state.keylen);")
save = create_element_instance("save", [Port("in", ["int", "uint8_t"])], [Port("out", [])],
    r'''(int len, uint8_t data) = in();
    state.key = (uint8_t *) malloc(len);
    state.keylen = len;
    for(int i=0; i<len ; i++)
        state.key[i] = data;
    output { out(); }''')

enq, deq = queue_smart.smart_circular_queue_variablesize_one2many_instances("queue", 256, 4, 1)

display = create_element_instance("display", [Port("in", [])], [],
                               r'''printf("%d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1]);''')

pipeline_state(save, "mystate")


@API("push", process="queue_shared_data1")
def run1(index):
    x = save(index)
    enq(x)


@API("pop", process="queue_shared_data2")
def run2(core):
    x = deq(core)
    display(x)

master_process("queue_shared_data1")

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "../queue.h"
#include "../shm.h"
'''

c.generate_code_as_header()
c.compile_and_run(["queue_shared_data1", "queue_shared_data2"])