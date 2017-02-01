from compiler import *
from thread_allocation import *

p = Program(
    Element("Forwarder",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''out(in());'''),
    Element("Comsumer",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n", in());'''),
    ElementInstance("Forwarder", "Forwarder"),
    ElementInstance("Comsumer", "Comsumer"),
    Connect("Forwarder", "Comsumer")
    , ExternalTrigger("Forwarder")
    , InternalTrigger("Comsumer")
)

g = generate_graph(p)
print g
generate_code(g)
