from compiler import *
from standard_elements import *

p = Program(
    Forward,
    Element("Comsumer",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n", in());'''),
    ElementInstance("Forward", "Forwarder"),
    ElementInstance("Comsumer", "Comsumer"),
    Connect("Forwarder", "Comsumer")
    , ExternalTrigger("Forwarder")
    , InternalTrigger("Comsumer")
)

g = generate_graph(p)
print g
generate_code(g)
