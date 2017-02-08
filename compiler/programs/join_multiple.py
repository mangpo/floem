from compiler import *
from standard_elements import *

p = Program(
            Fork2, Fork3, Forward, Add,
            ElementInstance("Fork3", "fork3"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork3", "f1", "out1"),
            Connect("fork3", "fork2", "out2"),
            Connect("fork3", "f2", "out3"),
            Connect("fork2", "add1", "out1", "in1"),
            Connect("fork2", "add2", "out2", "in1"),
            Connect("f1", "add1", "out", "in2"),
            Connect("f2", "add2", "out", "in2")
        )

g = generate_graph(p)
generate_code_and_run(g, "fork3(1);", [2,2])