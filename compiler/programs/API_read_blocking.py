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
    ExternalTrigger("f2"),
    APIFunction("read", "f2", [], "f2", ["out"], "ReadReturn")
)

g = generate_graph(p)
generate_code(g)