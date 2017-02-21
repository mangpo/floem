from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")

inc1 = Inc()
inc2 = Inc()
x = inc1(None)
y = inc2(x)

t = API_thread("add2", ["int"], "int")
t.run(True, inc1, inc2)

c = Compiler()
c.testing = "out(add2(11)); out(add2(0));"
c.generate_code_and_run([13,2])