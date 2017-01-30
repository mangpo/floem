from graph import *
from compiler import *

s = State("Buffer", "int x; int avail;", "0,0")

e1 = Element("Write",
             [Port("in", ["int"])],
             [],
             r'''if(this.avail==1) { printf("Failed.\n"); exit(-1); } this.x = in(); this.avail = 1;''',
             None,
             [("Buffer", "this")])

e2= Element("BlockingRead",
             [],
             [Port("in", ["int"])],
             r'''while(this.avail==0); int x = this.x; this.avail = 0; printf("%d\n", x);''',
             None,
             [("Buffer", "this")])

graph = Graph([e1, e2], [s])
graph.newStateInstance("Buffer", "s")
graph.newElementInstance("Write", "w", ["s"])
graph.newElementInstance("BlockingRead", "r", ["s"])
generate_code(graph)
