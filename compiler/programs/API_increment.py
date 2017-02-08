from compiler import *
from standard_elements import *

p = Program(
    Inc,
    ElementInstance("Inc", "inc1"),
    ElementInstance("Inc", "inc2"),
    Connect("inc1", "inc2"),
    APIFunction("add2", "inc1", "in", "inc2", "out", "int")
)

g = generate_graph(p)
generate_code_and_run(g, "out(add2(11)); out(add2(0));", [13,2])