from compiler import *
from thread_allocation import *

p = Program(
            Element("Fork2",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x);'''),
            Element("Fork3",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"]), Port("out3", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x); out3(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Add",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in1() + in2());'''),
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
print g
generate_code(g)