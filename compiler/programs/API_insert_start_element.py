from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")
Add = create_add("Add", "int")

@API("func")
def add2(x, offset):
    inc1 = Inc()
    inc2 = Inc()
    add1 = Add()
    add2 = Add()

    y1 = inc1(x)
    y2 = inc2(x)
    return add2(add1(y1, y2), offset)

c = Compiler()
c.testing = "out(func(1, 0)); out(func(2, 100));"
c.generate_code_and_run([4, 106])