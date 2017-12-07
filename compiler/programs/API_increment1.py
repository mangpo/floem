from library import *
from compiler import Compiler

inc1 = Inc('inc1', configure=[Int])
inc2 = Inc('inc2', configure=[Int])
inc1 >> inc2

t = APIThread('add2', ["int"], "int")
t.run(inc1, inc2)

c = Compiler()
c.testing = "out(add2(11)); out(add2(0));"
c.generate_code_and_run([13,2])

