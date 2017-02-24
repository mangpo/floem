from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")

def unit_func(x0, t1, t2):
    f1 = Forward()
    f2 = Forward()
    x1 = f1(x0)
    x2 = f2(x1)

    t1(f1)
    t2(f2)
    return x2

Unit = create_composite("Unit", unit_func)
unit = Unit()
pre = Forward()
post = Forward()

t1 = API_thread("write", ["int"], None)
t2 = API_thread("read", [], "int")

x1 = pre(None)
x2 = unit(x1)
x3 = post(x2)

unit(None, t1.run, t2.run_start)
t1.run_start(pre)
t2.run(post)

c = Compiler()
c.testing = "write(123); out(read()); write(42); out(read());"
c.generate_code_and_run([123,42])