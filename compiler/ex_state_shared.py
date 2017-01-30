from graph import *
from compiler import *

s = State("Shared", "int sum;", "100")

e1 = Element("Sum",
             [Port("in", ["int"])],
             [],
             r'''this.sum += in(); printf("%d\n", this.sum);''',
             None,
             [("Shared", "this")])

graph = Graph([e1], [s])
graph.newStateInstance("Shared", "s")
graph.newElementInstance("Sum", "sum1", ["s"])
graph.newElementInstance("Sum", "sum2", ["s"])
generate_code(graph)
