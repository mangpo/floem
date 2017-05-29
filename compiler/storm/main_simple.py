from elements_library import *
import queue_smart

Inject = create_inject("inject", "struct tuple*", 1000, "random_tuple")
inject = Inject()

task_master = create_state("task_master", "struct executor **task2executor;")
task_master_inst = task_master("my_task_master", ["get_task2executor()"])

exe_creator = create_element("exe_creator",
                              [Port("in", ["struct tuple*"])],
                              [],
                              r'''
    struct tuple* t = in();
    struct executor *exec = this->task2executor[t->task];
    assert(exec != NULL);
    exec->execute(t, exec);
                              ''',
                              None, [("task_master", "this")])

exe = exe_creator("exe", [task_master_inst])

spout_exe = create_element_instance("spout_exe",
                                     [Port("in", ["struct executor*"])],
                                     [],
                                     r'''
    struct executor *exec = in();
    assert(exec != NULL);
    exec->execute(NULL, exec);
                                    '''
                                     )

print_tuple_creator = create_element("print_tuple_creator",
                                      [Port("in", ["struct tuple*", "struct executor*"])], [],
                                      r'''
    (struct tuple* t, struct executor* exe) = in();

  t->fromtask = exe->taskid;
  t->task = exe->grouper(t, exe);
  t->starttime = rdtsc();

    printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
    //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[1].str, t->v[1].integer);
                                      ''')
print_tuple = print_tuple_creator()


@internal_trigger("run", process="simple")
def run():
    t = inject()
    exe(t)


@API("spout_run", process="simple")
def spout_run(executor):
    spout_exe(executor)


@API("tuple_send", process="simple")
def tuple_send(t):
    print_tuple(t)


c = Compiler()
c.include = r'''
#include "worker.h"
#include "storm.h"
'''
c.depend = ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker']
c.generate_code_as_header()
c.compile_and_run(["test_simple"])

# TODO:
# 1. control inject interval
# 2. create simple.h & simple.c, compile simple.o