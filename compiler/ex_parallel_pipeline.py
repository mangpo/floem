from ast import *
from compiler import *
from thread_allocation import *

e1 = Element("Forwarder",
             [Port("in", ["int"])],
             [Port("out", ["int"])],
             r'''out(in());''')
e2 = Element("Comsumer",
             [Port("in", ["int"])],
             [],
             r'''printf("%d\n", in());''')

graph = Graph([e1, e2])
graph.defineInstance("Forwarder", "Forwarder")
graph.defineInstance("Comsumer", "Comsumer")
graph.connect("Forwarder", "Comsumer")

allocator = ThreadAllocator(graph)
allocator.external_api("Forwarder")
allocator.internal_trigger("Comsumer") # 1 thread round-robin
# allocator.same_thread()
# allocator.spawn()

print "--------------- ORG ----------------"
generate_code(graph)
print "--------------- INFO -----------------"
allocator.transform()
print "--------------- CODE ----------------"
generate_code(graph)
