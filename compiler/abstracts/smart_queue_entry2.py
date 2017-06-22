from dsl import *
from elements_library import *
import queue_smart

state = create_state("mystate", "int a; int a0; int b0; size_t core;")
save = create_element_instance("save", [Port("in", ["int"])], [Port("out", [])],
                               r'''state.a = in(); state.core = 0; output { out(); }''')
classify = create_element_instance("classify",
                                   [Port("in", [])],
                                   [Port("out1", []), Port("out2", [])],
                                   r'''
    output switch { case (state.a % 2) == 0: out1();
                    else: out2(); }
                                   ''')

a0 = create_element_instance("a0", [Port("in", [])], [Port("out", [])], r'''state.a0 = state.a + 100; output { out(); }''')
b0 = create_element_instance("b0", [Port("in", [])], [Port("out", [])], r'''state.b0 = state.a * 2; output { out(); }''')

enq, deq, scan = queue_smart.smart_circular_queue_variablesize_one2many_instances("queue", 100, 4, 2)

a1 = create_element_instance("a1", [Port("in", [])], [], r'''printf("a1 %d\n", state.a0);''')
b1 = create_element_instance("b1", [Port("in", [])], [], r'''printf("b1 %d\n", state.b0);''')

pipeline_state(save, "mystate")

@API("run1")
def run1(x):
    a_in, b_in = classify(save(x))
    a0_out = a0(a_in)
    b0_out = b0(b_in)
    enq(a0_out, b0_out)

@API("run2")
def run2(core):
    a1_in, b1_in = deq(core)
    a1(a1_in)
    b1(b1_in)

c = Compiler()
c.include = r'''
#include "../queue.h"
'''
c.testing = "run1(123); run1(42); run2(0); run2(0);"
c.generate_code_and_run(['b1', 246, 'a1', 142])
