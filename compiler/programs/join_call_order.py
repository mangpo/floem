from compiler import *
from standard_elements import *

p = Program(
            Fork2, Fork3, Forward, Add,
            Element("Add3",
                    [Port("in1", ["int"]), Port("in2", ["int"]), Port("in3", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in1() + in2() + in3(); output { out(x); }'''),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Fork3", "fork3"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add2"),
            ElementInstance("Add3", "add3"),
            Connect("fork2", "f1", "out1"),
            Connect("fork2", "fork3", "out2"),
            Connect("fork3", "f2", "out3"),
            Connect("fork3", "f3", "out2"),
            Connect("f2", "add2", "out", "in1"),
            Connect("f3", "add2", "out", "in2"),
            Connect("f1", "add3", "out", "in1"),
            Connect("add2", "add3", "out", "in2"),
            Connect("fork3", "add3", "out1", "in3"),
        )

g = generate_graph(p)
generate_code_and_run(g, "fork2(1);", [4])
