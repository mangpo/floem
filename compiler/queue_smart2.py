from dsl2 import *
import graph_ir


def smart_queue(name, size, n_cores, n_cases, enq_blocking=False, deq_blocking=False,
                enq_atomic=False, deq_atomic=False, clean=False,
                enq_output=False):
    prefix = name + "_"
    queue = graph_ir.Queue(name, size, n_cores, n_cases, enq_blocking=enq_blocking, deq_blocking=deq_blocking,
                           enq_atomic=enq_atomic, deq_atomic=deq_atomic, enq_output=enq_output)

    class Enqueue(Element):
        def configure(self):
            self.inp = [Input() for i in range(n_cases)]
            self.special = queue
            if enq_output:
                self.done = Output()

        def impl(self):
            if enq_output:
                self.run_c("state.core; output { done(); }")
            else:
                self.run_c("state.core;")

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            queue.enq = self.instance

    class Dequeue(Element):
        def configure(self):
            self.inp = Input(Size)  # core
            self.out = [Output() for i in range(n_cases)]
            self.special = queue

        def impl(self):
            src = ""
            for i in range(n_cases):
                src += "out%d(); " % i
            self.run_c("output { %s }" % src)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            queue.deq = self.instance

    class Clean(Element):
        def configure(self):
            self.out = [Output() for i in range(n_cases)]
            self.special = queue

        def impl(self):
            src = ""
            for i in range(n_cases):
                src += "out%d(); " % i
            self.run_c("output { %s }" % src)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            queue.clean = self.instance

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Clean.__name__ = prefix + Clean.__name__

    return Enqueue, Dequeue, Clean if clean else None