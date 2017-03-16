from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')
p = Print()

f1 = Forward("f")

def spec(x):
    f1 = Forward()
    f2 = Forward()
    return f1(x), f2(x)

def impl(x):
    f1 = Forward("f1")
    f2 = Forward("f2")
    f3 = Forward("f3")
    return f1(x), f3(f2(x))

compo = create_spec_impl("compo", spec, impl)

x1, x2 = compo(f1(None))
p(x1)
p(x2)

t = API_thread("run", ["int"], None)
t.run_start(f1, compo, p)

c = Compiler()
c.desugar_mode = "compare"
try:
    c.generate_graph()
except Exception as e:
    assert e.message == "Resource 'run' has more than one starting element instance."

c.desugar_mode = "impl"
c.testing = "run(42);"
c.generate_code_and_run([42,42])
