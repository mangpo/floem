from compiler import *
from thread_allocation import *

p = Program(
    Element("Forward",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''out(in());'''),
    ElementInstance("Forward", "f1"),
    ElementInstance("Forward", "f2"),
    Connect("f1", "f2"),
    APIFunction("put", "f1", "in", "f1", None, None),
    APIFunction("get", "f2", None, "f2", "out", "int")
)

g = generate_graph(p)
generate_code(g)
