from ast import *
from compiler import *


e1 = Element("Fork",
             [Port("in", ["int","int"])],
             [Port("to_add", ["int","int"]), Port("to_sub", ["int","int"])],
             r'''(int x, int y) = in(); to_add(x,y); to_sub(x,y);''')
e2 = Element("Add",
             [Port("in", ["int","int"])],
             [Port("out", ["int"])],
             r'''(int x, int y) = in(); out(x+y);''')
e3 = Element("Sub",
             [Port("in", ["int","int"])],
             [Port("out", ["int"])],
             r'''(int x, int y) = in(); out(x-y);''')
e4 = Element("Print",
             [Port("in1", ["int"]), Port("in2", ["int"])],
             [],
             r'''printf("%d %d\n",in1(), in2());''')

graph = Graph([e1, e2, e3, e4])
graph.defineInstance("Fork", "Fork")
graph.defineInstance("Add", "Add")
graph.defineInstance("Sub", "Sub")
graph.defineInstance("Print", "Print")
graph.connect("Fork", "Add", "to_add")
graph.connect("Fork", "Sub", "to_sub")
graph.connect("Add", "Print", "out", "in1")
graph.connect("Sub", "Print", "out", "in2")

graph.internal_trigger("Sub")

print "--------------- ORG ----------------"
generateCode(graph)
print "--------------- INFO -----------------"
graph.assign_threads()
graph.insert_theading_elements()
graph.print_threads_info()
print "--------------- CODE ----------------"
generateCode(graph)

