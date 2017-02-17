from compiler import *
from standard_elements import *
from desugaring import desugar
from queue import *

instances, enq, deq = CircularQueueOneToMany("queue", "int", 4, 4)
tx_instances, tx_enq, tx_deq = CircularQueueManytoOne("tx_queue", "int", 4, 4)
statements = instances + tx_instances + \
             [
                 Element("ComputeCore",
                         [Port("in", ["size_t", "int"])],
                         [Port("out_value", ["int"]), Port("out_core", ["size_t"])],
                         r'''(size_t core, int x) = in(); output { out_value(x); out_core(core); }'''),
                 ElementInstance("ComputeCore", "core"),
                 Connect("core", enq.name, "out_value", "in_entry"),
                 Connect("core", enq.name, "out_core", "in_core"),
                 APIFunction("write", "core", "in", enq.name, None),
                 APIFunction("read[i]", deq.name.replace('[4]','[i]'), None,
                             deq.name.replace('[4]','[i]'), "out", "int"),

                 APIFunction("tx_write[i]", tx_enq.name.replace('[4]','[i]'), "in",
                             tx_enq.name.replace('[4]','[i]'), None),
                 APIFunction("tx_read", tx_deq.name, None, tx_deq.name, "out", "int")
             ]

testing = r'''
write(1,1);
write(2,2);
write(1,5);
out(read1());
out(read1());
out(read2());

tx_write0(0);
tx_write0(100);
tx_write3(3);
out(tx_read());
out(tx_read());
out(tx_read());
//out(tx_read());


tx_write0(11);
tx_write0(12);
tx_write0(13);
out(tx_read());
out(tx_read());
out(tx_read());
'''

p = Program(*statements)
dp = desugar(p)
g = generate_graph(dp)
generate_code_and_run(g,testing, [1,5,2,  0, 3, 100, 11, 12, 13])