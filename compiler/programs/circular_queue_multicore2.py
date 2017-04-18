from dsl import *
from elements_library import *
import queue

Gen = create_identity("gen", "int")
gen = Gen()
fork = create_fork_instance("myfork", 2, "int")

GetCore = create_element("GetCore",
                 [Port("in", ["int"])],
                 [Port("out", ["size_t"])],
                 r'''
(int x) = in();
output { out(x % 2); }
                 ''')

n_cores = 2
t = API_thread("run", ["int"], None)

def nic2app_func(x):
    get_core = GetCore()
    rx_enq, rx_deqs = queue.create_circular_queue_one2many_instances("rx_queue", "int", 4, n_cores)
    rx_enq(x, get_core(x))
    t.run(get_core, rx_enq)

    for i in range(n_cores):
        # api = API_thread("get_eq" + str(i), [], "eq_entry*", "NULL")
        # api.run(rx_deqs[i])
        @API("get_eq" + str(i), "NULL")
        def get_eq():
            return rx_deqs[i]()

nic2app = create_composite_instance("nic2app", nic2app_func)

x1, x2 = fork(gen())
nic2app(x1)
nic2app(x2)
t.run(gen, fork)

c = Compiler()
c.testing = r'''
run(1);
printf("%d\n", get_eq1());
printf("%d\n", get_eq1());

printf("%d\n", get_eq0());
printf("%d\n", get_eq1());

run(8);
printf("%d\n", get_eq0());
printf("%d\n", get_eq0());

printf("%d\n", get_eq0());
printf("%d\n", get_eq1());
'''
c.generate_code_and_run([1,1,0,0,8,8,0,0])