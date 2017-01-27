from ast import *
from compiler import *


e1 = Element("Sum",
             [Port("in", ["int"])],
             [],
             r'''this.sum += in(); printf("%d\n", this.sum);''',
             State("this", "int sum;", "100"))

graph = Graph([e1])
graph.defineInstance("Sum", "sum1")
graph.defineInstance("Sum", "sum2")
generateCode(graph)
