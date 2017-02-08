from compiler import *
from thread_allocation import *

p = Program(
    State("Count", "int count;", "0"),
    Element("Identity",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''local.count++; global.count++; int x = in(); printf("%d %d\n", local.count, global.count); output { out(x); }''',
            None,
            [("Count", "local"), ("Count", "global")]
            ),
    Composite("Unit",
              [Port("in", ("x1", "in"))],
              [Port("out", ("x2", "out"))],
              [],
              [("Count", "global")],
              Program(
                  StateInstance("Count", "local"),
                  ElementInstance("Identity", "x1", ["local", "global"]),
                  ElementInstance("Identity", "x2", ["local", "global"]),
                  Connect("x1", "x2") # error
                  #, InternalThread("x2")
              )),
    StateInstance("Count", "c"),
    Element("Print",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n", in());'''),
    CompositeInstance("Unit", "u1", ["c"]),
    CompositeInstance("Unit", "u2", ["c"]),
    ElementInstance("Print", "Print"),
    Connect("u1", "u2"),
    Connect("u2", "Print")
)

g = generate_graph(p)
generate_code_and_run(g, "u1_in(123); u1_in(42);", [1,1,2,2,1,3,2,4,123, 3,5,4,6,3,7,4,8,42])