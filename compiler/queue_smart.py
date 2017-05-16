import dsl
import graph


class Queue:
    def __init__(self, name, size, n_cores, n_cases):
        self.name = name
        self.size = size
        self.n_cores = n_cores
        self.n_cases = n_cases
        self.enq = None
        self.deq = None


class QueueVariableSizeOne2Many(Queue):
    def __init__(self, name, size, n_cores, n_cases):
        Queue.__init__(self, name, size, n_cores, n_cases)


def smart_circular_queue_variablesize_one2many(name, size, n_cores, n_cases):
    prefix = "_%s_" % name
    queue = QueueVariableSizeOne2Many(name, size, n_cores, n_cases)
    Smart_enq = dsl.create_element(prefix + "smart_enq_ele",
                                   [graph.Port("in" + str(i), []) for i in range(n_cases)],
                                   [graph.Port("out", [])],
                                   "state.core; output { out(); }",
                                   special=queue)

    src = ""
    for i in range(n_cases):
        src += "out%d(); " % i
    Smart_deq = dsl.create_element(prefix + "smart_deq_ele",
                                   [graph.Port("in_core", ["size_t"]), graph.Port("in", [])],
                                   [graph.Port("out" + str(i), []) for i in range(n_cases)],
                                   "output { %s }" % src,
                                   special=queue)

    return Smart_enq, Smart_deq, queue


def smart_circular_queue_variablesize_one2many_instances(name, size, n_cores, n_cases):
    Enq, Deq, queue = smart_circular_queue_variablesize_one2many(name, size, n_cores, n_cases)
    enq = Enq()
    deq = Deq()

    x = enq()
    deq(None, x)

    queue.enq = enq.instance
    queue.deq = deq.instance

    return enq, deq
