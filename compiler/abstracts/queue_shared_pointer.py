from elements_library import *
import queue_smart

create_memory_region("data_region", 4 * 100)

state = create_state("mystate", "int core; int index; int *p @shared(data_region);")
save = create_element_instance("save", [Port("in", ["int"])], [Port("out", [])],
                               r'''state.index = in(); state.p = data_region; state.core = 0; output { out(); }''')

enq, deq, scan = queue_smart.smart_circular_queue_variablesize_one2many_instances("queue", 256, 4, 1)

display = create_element_instance("display", [Port("in", [])], [],
                               r'''printf("%d\n", state.p[state.index]); fflush(stdout);''')

pipeline_state(save, "mystate")


@API("push", process="queue_shared_p1")
def run1(index):
    x = save(index)
    enq(x)


@API("pop", process="queue_shared_p2")
def run2(core):
    x = deq(core)
    display(x)

master_process("queue_shared_p1")

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
'''

c.generate_code_as_header()
c.depend = {"queue_shared_p1_main": ['queue_shared_p1'],
            "queue_shared_p2_main": ['queue_shared_p2']}
c.compile_and_run(["queue_shared_p1_main", "queue_shared_p2_main"])