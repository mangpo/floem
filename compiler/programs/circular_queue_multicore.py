import queue
from dsl import *

n_cores = 4

rx_enq, rx_deqs = queue.create_circular_queue_one2many_instances("rx_queue", "int", 4, n_cores)
tx_enqs, tx_deq = queue.create_circular_queue_many2one_instances("tx_queue", "int", 4, n_cores)
compute_core = create_element_instance("ComputeCore",
                         [Port("in", ["int", "size_t"])],
                         [Port("out_value", ["int"]), Port("out_core", ["size_t"])],
                         r'''(int x, size_t core) = in(); output { out_value(x); out_core(core); }''')

val1, core = compute_core(None)
rx_enq(val1, core)

rx_nic = API_thread("rx_write", ["int", "size_t"], None)
rx_apps = [API_thread("rx_read" + str(i), [], "int", "-1") for i in range(n_cores)]
tx_apps = [API_thread("tx_write" + str(i), ["int"], None) for i in range(n_cores)]
tx_nic = API_thread("tx_read", [], "int", "-1")

rx_nic.run(compute_core, rx_enq)
for i in range(n_cores):
    rx_apps[i].run(rx_deqs[i])
    tx_apps[i].run(tx_enqs[i])
tx_nic.run(tx_deq)

c = Compiler()
c.testing = r'''
rx_write(1,1);
rx_write(2,2);
rx_write(5,1);
out(rx_read1());
out(rx_read1());
out(rx_read2());

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

c.generate_code_and_run([1,5,2,  0, 3, 100, 11, 12, 13])