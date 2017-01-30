from compiler import *
from thread_allocation import *

p = Program(
    State("Buffer", "int x; int avail;", "0,0"),
    Element("Write",
            [Port("in", ["int"])],
            [],
            r'''if(this.avail==1) { printf("Failed.\n"); exit(-1); } this.x = in(); this.avail = 1;''',
            None,
            [("Buffer", "this")]),
    Element("BlockingRead",
            [],
            [Port("in", ["int"])],
            r'''while(this.avail==0); int x = this.x; this.avail = 0; printf("%d\n", x);''',
            None,
            [("Buffer", "this")]),
    StateInstance("Buffer", "s"),
    ElementInstance("Write", "w", ["s"]),
    ElementInstance("BlockingRead", "r", ["s"])
)

g = generate_graph(p)
print g
generate_code(g)