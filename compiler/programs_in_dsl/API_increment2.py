from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")

@API("add2")
def add2(x):
    inc1 = Inc()
    inc2 = Inc()
    return inc2(inc1(x))

c = Compiler()
c.testing = "out(add2(11)); out(add2(0));"
c.generate_code_and_run([13,2])