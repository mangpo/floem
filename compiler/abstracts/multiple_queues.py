from dsl import *
from elements_library import *
import queue_smart

choose = create_element_instance("choose",
                    [Port("in", ["int"])],
                    [Port("out0", []), Port("out1", [])],
                    r'''int x = in(); state.a = x; state.core = 1; output switch { case (x % 2 == 0): out0(); else: out1(); }''')
defA = create_element_instance("defA",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''output { out(); }''')
defB = create_element_instance("defB",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.b = state.a; output { out(); }''')
useA = create_element_instance("useA",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.c = state.a; output { out(); }''')
useB = create_element_instance("useB",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.c = state.b; output { out(); }''')
f = create_element_instance("f",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''output { out(); }''')
display = create_element_instance("display",
                    [Port("in", [])],
                    [],
                    r'''printf("%d\n", state.c);''')
enq1, deq1, scan1 = queue_smart.smart_circular_queue_variablesize_one2many_instances("queue1", 256, 2, 2)
enq2, deq2, scan2 = queue_smart.smart_circular_queue_variablesize_one2many_instances("queue2", 256, 2, 1)

state = create_state("mystate", "int core; int a; int b; int c;")

pipeline_state(choose, "mystate")

@API("run1")
def run1(x):
    x1, x2 = choose(x)
    y1 = defA(x1)
    y2 = defB(x2)
    enq1(y1, y2)

@API("run2")
def run2(core):
    x1, x2 = deq1(core)
    y1 = useA(x1)
    y2 = useB(x2)
    z = f(y1)
    z = f(y2)
    enq2(z)

@API("run3")
def run3(core):
    x = deq2(core)
    display(x)

c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
'''
c.testing = "run1(123); run1(42); run2(1); run3(1); run2(1); run3(1);"
c.generate_code_and_run([123, 42])
