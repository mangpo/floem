from elements_library import *
import queue
import net

test = "spout"
inject_func = "random_" + test
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 5
n_workers = 4

from_net = net.create_from_net_fixed_size("tuple", "struct tuple", n_workers, 8192, "workers[atoi(argv[1])].port")
to_nets = []
for i in range(n_workers):
    to_net = net.create_to_net_fixed_size("tuple" + str(i), "struct tuple", "workers[%d].hostname" % i, "workers[%d].port" % i)
    to_nets.append(to_net)

task_master = create_state("task_master", "int *task2executorid; int *task2worker;")
task_master_inst = task_master("my_task_master", ["get_task2executorid()", "get_task2worker()"])

get_core_creator = create_element("get_core_creator",
                              [Port("in", ["struct tuple*"])],
                              [Port("out", ["struct tuple*", "size_t"])],
                              r'''
    struct tuple* t = in();
    int id = this->task2executorid[t->task];
    printf("receive: task %d, id %d\n", t->task, id);
    output { out(t, id); }
                              ''',
                              None, [("task_master", "this")])

get_core = get_core_creator("get_core", [task_master_inst])
get_core2 = get_core_creator("get_core2", [task_master_inst])

choose_creator = create_element("choose_creator",
                                 [Port("in", ["struct tuple*"])],
                                 [Port("out_send", ["struct tuple*"]),
                                  Port("out_local", ["struct tuple*"]),
                                  Port("out_nop", [])],
                                 r'''
    struct tuple* t = in();
    bool local;
    if(t != NULL) {
        local = (this->task2worker[t->task] == this->task2worker[t->fromtask]);
        if(local) printf("send to myself!\n");
    }
    output switch { case (t && local): out_local(t); case (t && !local): out_send(t); else: out_nop(); }
                                 ''', None, [("task_master", "this")])
choose = choose_creator("choose", [task_master_inst])

print_tuple_creator = create_element("print_tuple_creator",
                                      [Port("in", ["struct tuple*"])], [Port("out", ["struct tuple*"])],
                                      r'''
    (struct tuple* t) = in();

    //printf("TUPLE = null\n");
    if(t != NULL) {
        printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
        //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[1].str, t->v[1].integer);
        fflush(stdout);
    }
    output { out(t); }
                                      ''')
print_tuple = print_tuple_creator()

src = ""
for i in range(n_workers):
    src += "case (id == {0}): out{0}(t); ".format(i)
steer_worker_creator = create_element("steer_worker_creator",
                                      [Port("in", ["struct tuple*"])],
                                      [Port("out" + str(i), ["struct tuple*"]) for i in range(n_workers)] +
                                      [Port("out_nop", [])],
                                      r'''
    (struct tuple* t) = in();
    int id = -1;
    if(t != NULL) {
        id = this->task2worker[t->task];
        printf("send to worker %d\n", id);
    }
    output switch { ''' + src + " else: out_nop(); }", None, [("task_master", "this")])

steer_worker = steer_worker_creator("steer_worker", [task_master_inst])

nop = create_element_instance("nop", [Port("in", [])], [], "")

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
    //printf("batch_size = %s\n", this->batch_size);
    if(this->batch_size >= BATCH_SIZE || rdtsc() - this->start >= BATCH_DELAY) {
        core = this->core;
        skip = this->batch_size;
        this->core = (this->core + 1) %s %d;
        this->batch_size = 0;
        if(skip>0) printf("advance: core = %s, skip = %s, %s >= %s\n", core, skip, rdtsc() - this->start, BATCH_DELAY);
        this->start = rdtsc();
    }

    output switch { case (skip>0): out(core, skip); }
                              ''' % ('%ld', '%', n_cores, '%ld', '%ld', '%.2ld', '%lf'),
                              None, [("queue_batch", "this")])

adv = adv_creator("adv", [my_queue_state])


MAX_ELEMS = (4 * 1024)
rx_enq_creator, rx_deq_creator, rx_adv_creator = \
    queue.create_copy_queue_many2many_inc_atomic("rx_queue", "struct tuple", MAX_ELEMS, n_cores, blocking=True)
tx_enq, tx_deq, tx_adv = queue.create_copy_queue_many2many_batch_instances("tx_queue", "struct tuple", MAX_ELEMS, n_cores)


@internal_trigger("nic_rx", process="flexstorm")
def nic_rx():
    t = from_net()
    t = get_core(t)
    rx_enq = rx_enq_creator("rx_queue_enq")
    rx_enq(t)


@API("inqueue_get", process="flexstorm")
def inqueue_get(core):
    rx_deq = rx_deq_creator("rx_queue_deq")
    return rx_deq(core)


@API("inqueue_advance", process="flexstorm")
def inqueue_advance(core):
    rx_adv = rx_adv_creator("rx_queue_adv")
    rx_adv(core)


@API("outqueue_put", process="flexstorm")
def outqueue_put(t):
    tx_enq(t)

@internal_trigger("nic_tx", process="flexstorm")
def nic_tx():
    core_i = queue_schedule()
    t = tx_deq(core_i)
    t = print_tuple(t)
    t_send, t_local, t_null = choose(t)

    # send
    ts = steer_worker(t_send)
    for i in range(n_workers):
        to_nets[i](ts[i])
    nop(ts[-1])

    # local
    t_local = get_core2(t_local)
    rx_enq2 = rx_enq_creator("rx_queue_enq2")
    rx_enq2(t_local)

    # nop
    nop(t_null)

    run_order(to_nets + [rx_enq2, nop], adv)  # TODO: this merging is very unly.
    core_i = adv(t)
    tx_adv(core_i)


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
