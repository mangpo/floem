from graph import *
from compiler import *
from thread_allocation import *


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
graph.newElementInstance("Fork", "Fork")
graph.newElementInstance("Add", "Add")
graph.newElementInstance("Sub", "Sub")
graph.newElementInstance("Print", "Print")
graph.connect("Fork", "Add", "to_add")
graph.connect("Fork", "Sub", "to_sub")
graph.connect("Add", "Print", "out", "in1")
graph.connect("Sub", "Print", "out", "in2")

allocator = ThreadAllocator(graph)
#allocator.internal_trigger("Sub")

print "--------------- ORG ----------------"
generate_code(graph)
print "--------------- INFO -----------------"
allocator.transform()
print "--------------- CODE ----------------"
generate_code(graph)

