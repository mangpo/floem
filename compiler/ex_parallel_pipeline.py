from ast import *
from compiler import *


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
graph.external_api("Forwarder")
graph.internal_trigger("Comsumer") # 1 thread round-robin
# graph.same_thread()
# graph.spawn()

print "--------------- ORG ----------------"
generateCode(graph)
print "--------------- INFO -----------------"
graph.assign_threads()
graph.insert_theading_elements()
graph.print_threads_info()
print "--------------- CODE ----------------"
generateCode(graph)
