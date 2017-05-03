from dsl import *
from elements_library import *

state = create_state("mystate", "int val;")
gen = create_element_instance("gen", [Port("in", ["int"])], [Port("out", [])], r'''state.val = in(); output { out(); }''')
display = create_element_instance("display", [Port("in", [])], [], r'''printf("%d\n", state.val);''')

pipeline_state(gen, "mystate")

@API("run")
def run(x):
    display(gen(x))

c = Compiler()
c.testing = "run(123); run(42);"
c.generate_code_and_run()
