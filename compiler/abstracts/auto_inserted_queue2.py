from dsl import *
from elements_library import *

state = create_state("mystate", "int a;")
gen = create_element_instance("gen", [Port("in", ["int"])], [Port("out", [])], "state.a = in(); output { out(); }")
display = create_element_instance("display", [Port("in", [])], [], r'''printf("%d\n", state.a);''')

display(gen(None))
pipeline_state(gen, "mystate")


t1 = API_thread("put", ["int"], None)
t2 = API_thread("get", [], None)
t1.run(gen)
t2.run(display)

CPU_process("p1", t1)
CPU_process("p2", t2)
master_process("p1")

c = Compiler()
c.testing = "put(42); get(); put(123); get();"
c.generate_code_and_run([42,123])