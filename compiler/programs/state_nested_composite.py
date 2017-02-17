from compiler import *
from thread_allocation import *

p = Program(
    State("Count", "int count;", "{0}"),
    Element("Identity",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''this.count++; int x = in(); output { out(this.count); }''',
            None,
            [("Count", "this")]
            ),
    Element("Print",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n", in());'''),
    Composite("Unit1",
              [Port("in", ("x1", "in"))], # error
              [Port("out", ("x1", "out"))],
              [],
              [("Count", "c")],
              Program(
                  ElementInstance("Identity", "x1", ["c"])
              )),
    Composite("Unit2",
              [Port("in", ("u1", "in"))], # error
              [Port("out", ("u1", "out"))],
              [],
              [("Count", "c1")],
              Program(
                  CompositeInstance("Unit1", "u1", ["c1"])
              )),
    StateInstance("Count", "c2"),
    CompositeInstance("Unit2", "u2", ["c2"]),
    ElementInstance("Print", "Print"),
    Connect("u2", "Print")
)

g = generate_graph(p)
generate_code_and_run(g, "u2_in(11); u2_in(22); u2_in(33);", [1,2,3])
