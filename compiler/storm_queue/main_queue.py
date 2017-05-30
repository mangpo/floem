from elements_library import *
import queue

n_cores = 4

Inject = create_inject("inject", "struct tuple*", 1000, "random_tuple", 1000000)
inject = Inject()

task_master = create_state("task_master", "int *task2executorid;")
task_master_inst = task_master("my_task_master", ["get_task2executorid()"])

get_core_creator = create_element("get_core_creator",
                              [Port("in", ["struct tuple*"])],
                              [Port("out", ["struct tuple*", "size_t"])],
                              r'''
    struct tuple* t = in();
    size_t id = this->task2executorid[t->task];
    output { out(t, id); }
                              ''',
                              None, [("task_master", "this")])

get_core = get_core_creator("get_core", [task_master_inst])

print_tuple_creator = create_element("print_tuple_creator",
                                      [Port("in", ["struct tuple*"])], [Port("out", ["struct tuple*"])],
                                      r'''
    (struct tuple* t) = in();

    if(t != NULL) {
        printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
        //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[1].str, t->v[1].integer);
        fflush(stdout);
    }
    output { out(t); }
                                      ''')
print_tuple = print_tuple_creator()

queue_state = create_state("queue_state", "int core;")
my_queue_state = queue_state("my_queue_state", [0])

queue_schedule_creator = create_element("queue_schedule_creator",
                              [],
                              [Port("out", ["size_t"])],
                              r'''
    int core = this->core;
    this->core = this->core %s %d;
    output { out(core); }
                              ''' % ('%', n_cores),
                              None, [("queue_state", "this")])

queue_schedule = queue_schedule_creator("queue_schedule", [my_queue_state])

adv = create_element_instance("adv",
                              [Port("in_val", ["struct tuple*"]), Port("in_core", ["size_t"])],
                              [Port("out", ["size_t"])],
                              r'''
    (struct tuple* t) = in_val();
    (size_t core) = in_core();
    output switch { case (t != NULL): out(core); }
                              ''')

MAX_ELEMS = (4 * 1024)
rx_enq, rx_deq, rx_adv = queue.create_copy_queue_many2many_inc_instances("rx_queue", "struct tuple", MAX_ELEMS, n_cores, blocking=True)
tx_enq, tx_deq, tx_adv = queue.create_copy_queue_many2many_inc_instances("tx_queue", "struct tuple", MAX_ELEMS, n_cores, blocking=False)


@internal_trigger("nic_rx", process="flexstorm")
def nic_rx():
    t = inject()
    t = get_core(t)
    rx_enq(t)


@API("inqueue_get", process="flexstorm")
def inqueue_get(core):
    return rx_deq(core)


@API("inqueue_advance", process="flexstorm")
def inqueue_advance(core):
    rx_adv(core)


@API("outqueue_put", process="flexstorm")
def outqueue_put(t):
    tx_enq(t)


@internal_trigger("nic_tx", process="flexstorm")
def nic_tx():
    core = queue_schedule()
    t = tx_deq(core)
    t = print_tuple(t)
    core = adv(t, core)
    tx_adv(core)

    run_order(print_tuple, tx_adv)


c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "worker.h"
#include "storm.h"
'''
c.depend = ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'flexstorm']
c.generate_code_as_header("flexstorm")
c.compile_and_run([("test_storm", 2)])
