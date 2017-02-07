from compiler import *
from standard_elements import *

p = Program(
            Fork2, Forward,
            ElementInstance("Fork2", "dup"),
            ElementInstance("Forward", "fwd"),
            Connect("dup", "fwd", "out1"),
            #InternalTrigger("fwd"),
            APIFunction("func1", "dup", "in", "dup", "out2", "int"),
            APIFunction("func2", "fwd", None, "fwd", "out", "int")
        )
g = generate_graph(p)
generate_code(g)
