from compiler import *
from thread_allocation import *

p = Program(
    Element("Identity",
             [Port("in", ["int"])],
             [Port("out", ["int"])],
             r'''out(in());'''),
    Composite("Unit",
              [Port("in", ("x1", "in"))],
              [Port("out", ("x2", "out"))],
              [],
              Program(
                  ElementInstance("Identity", "x1"),
                  ElementInstance("Identity", "x2"),
                  Connect("x1", "x2"),
                  InternalThread("x2")
              )),
    CompositeInstance("Unit", "u1"),
    CompositeInstance("Unit", "u2"),
    Connect("u1", "u2")
)

g = generate_graph(p)
print g
generate_code(g)