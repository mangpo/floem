from compiler import *

p = Program(
            Element("Dup",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''int x = in(); out1(x); out2(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Dup", "dup"),
            ElementInstance("Forward", "fwd"),
            Connect("dup", "fwd", "out1"),
            InternalTrigger("fwd"),
            APIFunction("func", "dup", "in", "dup", "out2", "FuncReturn")
        )
g = generate_graph(p)
generate_code(g)
