from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
f = Forward()
g = Forward()

g(f(None))

def assign_func(spec):
    if spec:
        t1 = APIFunction2("all", ["int"], int)
        t1.run_start(f, g)
    else:
        t1 = APIFunction2("write", ["int"], None)
        t1.run_start(f)
        t2 = APIFunction2("read", [], "int")
        t2.run_start(g)

dummy = create_spec_impl_instance("dummy", assign_func)

def run_spec():
    c = Compiler()
    c.desugar_mode = "spec"
    c.testing = "out(all(42)); out(all(123)); out(all(999));"
    c.generate_code_and_run([42,123,999])

def run_impl():
    c = Compiler()
    c.desugar_mode = "impl"
    c.testing = "write(42); out(read()); write(123); out(read()); write(999); out(read());"
    c.generate_code_and_run([42,123,999])
