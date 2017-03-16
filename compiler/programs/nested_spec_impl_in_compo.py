from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")

def compo(x):
    def spec(x):
        f = Inc("f_spec")
        return f(x)

    def impl(x):
        f = Inc("f_impl")
        g = Inc("g_impl")
        return g(f(x))

    spec_impl = create_spec_impl("inner", spec, impl)
    return spec_impl(x)

f = Inc("f")
compo = create_composite_instance("outer", compo)

compo(f(None))

t = API_thread("run", ["int"], "int")
t.run_start(f, compo)

c = Compiler()
c.testing = "out(run(0));"

c.desugar_mode = "spec"
c.generate_code_and_run([2])

c.desugar_mode = "impl"
c.generate_code_and_run([3])