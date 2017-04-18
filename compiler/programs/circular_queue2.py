from dsl import *
from elements_library import *
from queue import *

Inc = create_add1("Inc", "int")
inc1 = Inc()
inc2 = Inc()
queue = create_circular_queue_instance("queue", "int", 4)

inc2(queue(inc1(None)))

t1 = API_thread("enqueue", ["int"], None)
t2 = API_thread("dequeue", [], "int", "-1")

t1.run(inc1)
queue(None, t1, t2)
t2.run(inc2)

c = Compiler()
c.testing = "enqueue(1); enqueue(4); enqueue(9); out(dequeue()); out(dequeue()); out(dequeue()); enqueue(0); enqueue(2); out(dequeue()); out(dequeue());"
c.generate_code_and_run([3, 6, 11, 2, 4])