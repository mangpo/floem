from compiler import *
from thread_allocation import *

p = Program(
    Element("Fork",
            [Port("in", ["int","int"])],
            [Port("to_add", ["int","int"]), Port("to_sub", ["int","int"])],
            r'''(int x, int y) = in(); output { to_add(x,y); to_sub(x,y); }'''),
    Element("Add",
            [Port("in", ["int","int"])],
            [Port("out", ["int"])],
            r'''(int x, int y) = in(); output { out(x+y); }'''),
    Element("Sub",
            [Port("in", ["int","int"])],
            [Port("out", ["int"])],
            r'''(int x, int y) = in(); output { out(x-y); }'''),
    Element("Print",
            [Port("in1", ["int"]), Port("in2", ["int"])],
            [],
            r'''printf("%d %d\n",in1(), in2());'''),
    ElementInstance("Fork", "Fork"),
    ElementInstance("Add", "Add"),
    ElementInstance("Sub", "Sub"),
    ElementInstance("Print", "Print"),
    Connect("Fork", "Add", "to_add"),
    Connect("Fork", "Sub", "to_sub"),
    Connect("Add", "Print", "out", "in1"),
    Connect("Sub", "Print", "out", "in2"),
    InternalTrigger("Print")
)


g = generate_graph(p)
print g
generate_code(g)
