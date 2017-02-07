from compiler import *
from standard_elements import *

p = Program(
    Forward,
    Composite("Unit",
              [Port("in", ("f1", "in"))],
              [Port("out", ("f2", "out"))],
              [Port("tin", ("f2", None))],
              [],
              Program(
                  ElementInstance("Forward", "f1"),
                  ElementInstance("Forward", "f2"),
                  Connect("f1", "f2"),
                  ExternalTrigger("f2")
              )),
    CompositeInstance("Unit","u"),
    APIFunction("read", "u", "tin", "u", "out", "int")
)

g = generate_graph(p)
generate_code(g)