from library_dsl2 import *
from compiler import Compiler

f = Identity(configure=[Int])
g = Identity(configure=[Int])

f >> g

class test(Composite):
    def spec(self):
        t1 = APIThread("all", ["int"], "int")
        t1.run(f, g)

    def impl(self):
        t1 = APIThread("put", ["int"], None)
        t1.run(f)
        t2 = APIThread("get", [], "int")
        t2.run(g)

test()

def run_spec():
    c = Compiler()
    c.desugar_mode = "spec"
    c.testing = "out(all(42)); out(all(123)); out(all(999));"
    c.generate_code_and_run([42,123,999])

def run_impl():
    c = Compiler()
    c.desugar_mode = "impl"
    c.testing = "put(42); out(get()); put(123); out(get()); put(999); out(get());"
    c.generate_code_and_run([42,123,999])

run_spec()
#run_impl()