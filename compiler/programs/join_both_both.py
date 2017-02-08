from compiler import *
from standard_elements import *

p = Program(
            Fork2, Forward, Add,
            ElementInstance("Fork2", "a"),
            ElementInstance("Fork2", "b1"),
            ElementInstance("Fork2", "b2"),
            ElementInstance("Forward", "c1"),
            ElementInstance("Forward", "c2"),
            ElementInstance("Add", "d"),
            Connect("a", "b1", "out1"),
            Connect("a", "b2", "out2"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c2", "out1"),
            Connect("b2", "c1", "out2"),
            Connect("c1", "d", "out", "in1"),
            Connect("c2", "d", "out", "in2"),
        )

g = generate_graph(p)
generate_code_and_run(g, "a(1);", [2,2])