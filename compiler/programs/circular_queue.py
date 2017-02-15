from compiler import *
from standard_elements import *
from desugaring import desugar

p = Program(
    Inc, CircularQueue("Queue", "int", 4),
    ElementInstance("Inc", "inc1"),
    ElementInstance("Inc", "inc2"),
    CompositeInstance("Queue", "queue"),
    Connect("inc1", "queue"),
    Connect("queue", "inc2"),
    APIFunction("dequeue", "queue", "dequeue", "inc2", "out", "int")
)

g = generate_graph(desugar(p))
generate_code_and_run(g, "inc1(1); inc1(4); inc1(9); out(dequeue()); out(dequeue()); out(dequeue()); inc1(0); inc1(2); out(dequeue()); out(dequeue());", [3, 6, 11, 2, 4])