from elements_library import *
import queue
import net

test = "spout"
inject_func = "random_" + test
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 4

# Inject = create_inject("inject", "struct tuple*", 1000, inject_func, 1000000)
# inject = Inject()
from_net = net.create_from_net_fixed_size("tuple", "struct tuple", 4, 8192, 7001)  # workers[workerid].port, pass argv to init_instances
to_net = net.create_to_net_fixed_size("tuple", "struct tuple", "127.0.0.1", 7001)  # workers[i].hostname, workers[i].port, array of to_net

task_master = create_state("task_master", "int *task2executorid;")
task_master_inst = task_master("my_task_master", ["get_task2executorid()"])

get_core_creator = create_element("get_core_creator",
                              [Port("in", ["struct tuple*"])],
                              [Port("out", ["struct tuple*", "size_t"])],
                              r'''
    struct tuple* t = in();
    int id = -1;
    if(t != NULL) {
        id = this->task2executorid[t->task];
        printf("receive: task %d, id %d\n", t->task, id);
    }
    output switch { case (id >= 0): out(t, id); }
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


#######################################
# queue_state = create_state("queue_state", "int core;")
# my_queue_state = queue_state("my_queue_state", [0])
#
# queue_schedule_simple = create_element("queue_schedule_simple",
#                               [],
#                               [Port("out", ["size_t"])],
#                               r'''
#     int core = this->core;
#     this->core = (this->core + 1) %s %d;
#     output { out(core); }
#                               ''' % ('%', n_cores),
#                               None, [("queue_state", "this")])
#
# queue_schedule = queue_schedule_simple("queue_schedule", [my_queue_state])
#
# adv = create_element_instance("adv",
#                               [Port("in_val", ["struct tuple*"]), Port("in_core", ["size_t"])],
#                               [Port("out", ["size_t"])],
#                               r'''
#     (struct tuple* t) = in_val();
#     (size_t core) = in_core();
#     if(t != NULL) { printf("tx_deq: core = %d\n", core); fflush(stdout); }
#     output switch { case (t != NULL): out(core); }
#                               ''')

#######################################

queue_state = create_state("queue_batch", "int core; int batch_size; uint64_t start;")
my_queue_state = queue_state("my_queue_batch", [0, 0, 0, 0])

queue_schedule_batch = create_element("queue_schedule_batch",
                              [],
                              [Port("out", ["size_t", "size_t"])],
                              r'''
    output { out(this->core, this->batch_size); }
                              ''',
                              None, [("queue_batch", "this")])

queue_schedule = queue_schedule_batch("queue_schedule", [my_queue_state])

adv_creator = create_element("adv_creator",
                              [Port("in", ["struct tuple*"])],
                              [Port("out", ["size_t", "size_t"])],
                              r'''
    (struct tuple* t) = in();
    size_t core = 0;
    size_t skip = 0;
    if(t != NULL) this->batch_size++;
    if(this->batch_size >= BATCH_SIZE || rdtsc() - this->start >= BATCH_DELAY) {
        core = this->core;
        skip = this->batch_size;
        this->core = (this->core + 1) %s %d;
        this->batch_size = 0;
        if(skip>0) printf("advance: core = %s, skip = %s, %s >= %s\n", core, skip, rdtsc() - this->start, BATCH_DELAY);
        this->start = rdtsc();
    }

    output switch { case (skip>0): out(core, skip); }
                              ''' % ('%', n_cores, '%ld', '%ld', '%.2ld', '%lf'),
                              None, [("queue_batch", "this")])

adv = adv_creator("adv", [my_queue_state])

MAX_ELEMS = 8 #(4 * 1024)
rx_enq, rx_deq, rx_adv = queue.create_copy_queue_many2many_inc_instances("rx_queue", "struct tuple", MAX_ELEMS, n_cores, blocking=True)
#tx_enq, tx_deq, tx_adv = queue.create_copy_queue_many2many_inc_instances("tx_queue", "struct tuple", MAX_ELEMS, n_cores, blocking=False)
tx_enq, tx_deq, tx_adv = queue.create_copy_queue_many2many_batch_instances("tx_queue", "struct tuple", MAX_ELEMS, n_cores)


@internal_trigger("nic_rx", process="flexstorm")
def nic_rx():
    t = from_net()
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


# @internal_trigger("nic_tx", process="flexstorm")
# def nic_tx():
#     core = queue_schedule()
#     t = tx_deq(core)
#     t = print_tuple(t)
#     core = adv(t, core)
#     tx_adv(core)
#
#     run_order(print_tuple, tx_adv)

@internal_trigger("nic_tx", process="flexstorm")
def nic_tx():
    core_i = queue_schedule()
    t = tx_deq(core_i)
    t = print_tuple(t)
    to_net(t)
    core_i = adv(t)
    tx_adv(core_i)

run_order(print_tuple, tx_adv)


c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "worker.h"
#include "storm.h"
#include "../net.h"
'''
c.depend = {"test_storm": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'flexstorm']}
c.generate_code_as_header("flexstorm")
c.compile_and_run([("test_storm", workerid[test])])
