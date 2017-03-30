import queue
from dsl import *

n_cores = 4

s = create_state("my_entry", "uint16_t flags; uint16_t len; int val;")

enq_alloc, enq_submit, deq_get, deq_release = queue.create_circular_queue_variablesize_one2many_instances("rx_queue", 30, n_cores)
compute_core = create_element_instance("ComputeCore",
                         [Port("in", ["int", "size_t"])],
                         [Port("out_value", ["int"]), Port("out_core", ["size_t"]), Port("out_len", ["size_t"])],
                         r'''(int x, size_t core) = in(); output { out_value(x); out_core(core); out_len(4); }''')
fill_entry = create_element_instance("fill_entry",
                         [Port("in_entry", ["q_entry*"]), Port("in_value", ["int"])],
                         [Port("out", ["q_entry*"])],
                         r'''
    my_entry* e = (my_entry*) in_entry();
    (int v) = in_value();
    if(e != NULL) {
      e->val = v;
      printf("%d enq\n", v);
      }
    output switch { case (e != NULL): out((q_entry*) e); }''')

val, core, length = compute_core(None)
entry = enq_alloc(length, core)
entry = fill_entry(entry, val)
enq_submit(entry)

rx_nic = API_thread("rx_write", ["int", "size_t"], None)
rx_app = API_thread("rx_read", ["size_t"], "q_entry*")
rx_app_release = API_thread("rx_release", ["q_entry*"], None)

rx_nic.run_start(compute_core, enq_alloc, fill_entry, enq_submit)
rx_app.run_start(deq_get)
rx_app_release.run_start(deq_release)

c = Compiler()
c.include = r'''#include "../queue.h"'''
c.testing = r'''
my_entry* e;
rx_write(1,1);
rx_write(2,2);
rx_write(5,1);

e = (my_entry*) rx_read(1);
//printf("out_entry = %ld\n", e);
out(e->val);
rx_release((q_entry*) e);

e = (my_entry*) rx_read(1);
//printf("out_entry = %ld\n", e);
out(e->val);
rx_release((q_entry*) e);

e = (my_entry*) rx_read(2);
//printf("out_entry = %ld\n", e);
out(e->val);
rx_release((q_entry*) e);

e = (my_entry*) rx_read(2);
out(e);


rx_write(11,1);
rx_write(12,1);
rx_write(13,1);
rx_write(14,1);
e = (my_entry*) rx_read(1);
out(e->val);
rx_release((q_entry*) e);
rx_write(14,1);

'''

c.generate_code_and_run([1,"enq",2,"enq", 5, "enq", 1, 5, 2, 0, 11, "enq", 12, "enq", 13, "enq", 11, 14, "enq"])