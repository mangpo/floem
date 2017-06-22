import dsl
import graph
import queue_smart2


def smart_circular_queue_variablesize_one2many(name, size, n_cores, n_cases):
    prefix = "_%s_" % name
    queue = queue_smart2.Queue(name, size, n_cores, n_cases)
    Smart_enq = dsl.create_element(prefix + "smart_enq_ele", [graph.Port("inp" + str(i), []) for i in range(n_cases)],
                                   [graph.Port("out", [])], "state.core; output { out(); }", special=queue)

    src = ""
    for i in range(n_cases):
        src += "out%d(); " % i
    Smart_deq = dsl.create_element(prefix + "smart_deq_ele", [graph.Port("inp", ["size_t"]), graph.Port("in", [])],
                                   [graph.Port("out" + str(i), []) for i in range(n_cases)], "output { %s }" % src,
                                   special=queue)

    Scan = dsl.create_element(prefix + "smart_scan_ele", [graph.Port("in_core", ["size_t"])],
                                   [graph.Port("out" + str(i), []) for i in range(n_cases)], "output { %s }" % src,
                                   special=queue)

    return Smart_enq, Smart_deq, Scan, queue


def smart_circular_queue_variablesize_one2many_instances(name, size, n_cores, n_cases, clean=False):
    Enq, Deq, Scan, queue = smart_circular_queue_variablesize_one2many(name, size, n_cores, n_cases)
    enq = Enq()
    deq = Deq()

    x = enq()
    deq(None, x)

    queue.enq = enq.instance
    queue.deq = deq.instance
    if clean:
        scan = Scan()
        queue.scan = scan.instance
        queue.scan_type = clean
    else:
        scan = None

    return enq, deq, scan

#
# def smart_circular_queue_variablesize_many2one(name, size, n_cores, n_cases):
#     prefix = "_%s_" % name
#     queue = queue_ast.QueueVariableSizeMany2One(name, size, n_cores, n_cases)
#     Smart_enq = dsl.create_element(prefix + "smart_enq_ele", [graph.Port("inp" + str(i), []) for i in range(n_cases)],
#                                    [graph.Port("out", [])], "state.core; output { out(); }", special=queue)
#
#     src = ""
#     for i in range(n_cases):
#         src += "out%d(); " % i
#     Smart_deq = dsl.create_element(prefix + "smart_deq_ele", [graph.Port("inp", [])],
#                                    [graph.Port("out" + str(i), []) for i in range(n_cases)], "output { %s }" % src,
#                                    special=queue)
#
#     Scan = dsl.create_element(prefix + "smart_scan_ele", [graph.Port("in_core", ["size_t"])],
#                               [graph.Port("out" + str(i), []) for i in range(n_cases)], "output { %s }" % src,
#                               special=queue)
#
#     return Smart_enq, Smart_deq, Scan, queue
#
#
# def smart_circular_queue_variablesize_many2one_instances(name, size, n_cores, n_cases, clean=False):
#     Enq, Deq, Scan, queue = smart_circular_queue_variablesize_many2one(name, size, n_cores, n_cases)
#     enq = Enq()
#     deq = Deq()
#
#     x = enq()
#     deq(x)
#
#     queue.enq = enq.instance
#     queue.deq = deq.instance
#     if clean:
#         scan = Scan()
#         queue.scan = scan.instance
#         queue.scan_type = clean
#     else:
#         scan = None
#
#     return enq, deq, scan