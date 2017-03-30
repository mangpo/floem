import queue
from dsl import *

n_cores = 4

s = create_state("my_entry", "uint16_t flags; uint16_t len; int val;")

enq_alloc, enq_submit, deq_get, deq_release = \
    queue.create_circular_queue_variablesize_one2many_instances("rx_queue", 30, n_cores)
tx_enq_alloc, tx_enq_submit, tx_deq_get, tx_deq_release = \
    queue.create_circular_queue_variablesize_many2one_instances("tx_queue", 30, n_cores)
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

print_msg = create_element_instance("print_msg",
                         [Port("in", ["q_entry*"])],
                         [Port("out", ["q_entry*"])],
                         r'''
    my_entry* e = (my_entry*) in();
    printf("%d final\n", e->val);
    output { out((q_entry*) e); }''')

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

entry = tx_deq_get()
entry = print_msg(entry)
tx_deq_release(entry)

tx_nic = API_thread("tx_read", [], None)
tx_app = API_thread("tx_alloc", ["size_t","size_t"], "q_entry*")
tx_app_submit = API_thread("tx_submit", ["q_entry*"], None)

tx_nic.run_start(tx_deq_get, print_msg, tx_deq_release)
tx_app.run_start(tx_enq_alloc)
tx_app_submit.run_start(tx_enq_submit)


c = Compiler()
c.include = r'''#include "../queue.h"'''
c.testing = r'''
my_entry *e, *d;
rx_write(1,1);
rx_write(22,2);
rx_write(11,1);

e = (my_entry*) rx_read(1);
out(e->val);
d = (my_entry*) tx_alloc(1,sizeof(int));
d->val = e->val;
rx_release((q_entry*) e);
tx_submit((q_entry*) d);

e = (my_entry*) rx_read(1);
out(e->val);
d = (my_entry*) tx_alloc(1,sizeof(int));
d->val = e->val;
rx_release((q_entry*) e);
tx_submit((q_entry*) d);

e = (my_entry*) rx_read(2);
out(e->val);
d = (my_entry*) tx_alloc(2,sizeof(int));
d->val = e->val;
rx_release((q_entry*) e);
tx_submit((q_entry*) d);

tx_read();
tx_read();
tx_read();

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

c.generate_code_and_run() #[1,"enq",22,"enq", 11, "enq", 1, 11, 22,
                         #1, "final", 22, "final", 11, "final",
                         #0, 11, "enq", 12, "enq", 13, "enq", 11, 14, "enq"])