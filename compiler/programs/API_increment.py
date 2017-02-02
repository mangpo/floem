from compiler import *
from thread_allocation import *

p = Program(
    Element("Inc",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''out(in() + 1);'''),
    ElementInstance("Inc", "inc1"),
    ElementInstance("Inc", "inc2"),
    Connect("inc1", "inc2"),
    APIFunction("add2", "inc1", "in", "inc2", "out", "Add2Return")
)

g = generate_graph(p)
generate_code(g)