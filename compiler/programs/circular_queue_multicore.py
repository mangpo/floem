from compiler import *
from standard_elements import *
from desugaring import desugar
from queue import *

instances, enq, deq = CircularQueueOneToMany("queue", "int", 8, 4)
statements = instances + \
             [
                 Element("ComputeCore",
                         [Port("in", ["int"])],
                         [Port("out_value", ["int"]), Port("out_core", ["size_t"])],
                         r'''int x = in(); size_t core = x % 4; output { out_value(x); out_core(core); }'''),
                 ElementInstance("ComputeCore", "core"),
                 Connect("core", enq.name, "out_value", "in_entry"),
                 Connect("core", enq.name, "out_core", "in_core"),
                 APIFunction("write", "core", "in", enq.name, None),
                 APIFunction("read[i]", deq.name.replace('[4]','[i]'), None,
                             deq.name.replace('[4]','[i]'), "out", "int")
             ]

testing = r'''
write(1);
write(2);
write(5);
out(read1());
out(read1());
out(read2());
'''

p = Program(*statements)
dp = desugar(p)
g = generate_graph(dp)
generate_code_and_run(g,testing, [1,5,2])