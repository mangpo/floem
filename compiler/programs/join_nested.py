from compiler import *
from thread_allocation import *

p = Program(
            Element("Fork2",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Add",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in1() + in2());'''),
            ElementInstance("Fork2", "fork1"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork1", "fork2", "out1"),
            Connect("fork1", "f3", "out2"),
            Connect("fork2", "f1", "out1"),
            Connect("fork2", "f2", "out2"),
            Connect("f1", "add1", "out", "in1"),
            Connect("f2", "add1", "out", "in2"),
            Connect("add1", "add2", "out", "in1"),
            Connect("f3", "add2", "out", "in2")
        )

g = generate_graph(p)
print g
generate_code(g)
