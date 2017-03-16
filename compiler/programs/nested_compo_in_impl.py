from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")

def spec(x):
    f = Inc("f_spec")
    return f(x)

def impl(x):
    def compo(x):
        f = Inc()
        g = Inc()
        return g(f(x))
    compo_inst = create_composite_instance("compo", compo)
    return compo_inst(x)

spec_impl = create_spec_impl("outer", spec, impl)

f = Inc("f")

spec_impl(f(None))

t = API_thread("run", ["int"], "int")
t.run_start(f, spec_impl)

c = Compiler()
c.testing = "out(run(0));"

c.desugar_mode = "spec"
c.generate_code_and_run([2])

c.desugar_mode = "impl"
c.generate_code_and_run([3])