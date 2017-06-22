from dsl2 import *

class Queue:
    def __init__(self, name, size, n_cores, n_cases, blocking=False, enq_atomic=False, deq_atomic=False):
        self.name = name
        self.size = size
        self.n_cores = n_cores
        self.n_cases = n_cases
        self.enq = None
        self.deq = None
        self.scan = None
        self.scan_type = None
        self.blocking = blocking
        self.enq_atomic = enq_atomic
        self.deq_atomic = deq_atomic


def smart_queue(name, size, n_cores, n_cases, blocking=False, enq_atomic=False, deq_atomic=False, clean=False):
    prefix = name + "_"
    queue = Queue(name, size, n_cores, n_cases, blocking=blocking, enq_atomic=enq_atomic, deq_atomic=deq_atomic)

    class Enqueue(Element):
        def configure(self):
            self.inp = [Input() for i in range(n_cases)]
            self.special = queue

        def impl(self): self.run_c("state.core;")

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

    class Scan(Element):
        def configure(self):
            self.inp = Input(Size)  # core
            self.out = [Output() for i in range(n_cases)]
            self.special = queue
            queue.scan = self.instance

        def impl(self):
            src = ""
            for i in range(n_cases):
                src += "out%d(); " % i
            self.run_c("output { %s }" % src)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            queue.scan = self.instance

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Scan.__name__ = prefix + Scan.__name__

    return Enqueue, Dequeue, Scan