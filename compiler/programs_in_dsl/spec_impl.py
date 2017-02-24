from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
f = Forward()
g = Forward()

g(f(None))


def spec():
    t1 = API_thread("all", ["int"], "int")
    t1.run_start(f, g)

def impl():
    t1 = API_thread("write", ["int"], None)
    t1.run_start(f)
    t2 = API_thread("read", [], "int")
    t2.run_start(g)

mapping = create_spec_impl("mapping", spec, impl)

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

run_spec()
run_impl()