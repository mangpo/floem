from compiler import *
from standard_elements import *
from desugaring import desugar

p = Program(
    Inc, CircularQueue("Queue", "int", 4),
    ElementInstance("Inc", "inc1"),
    ElementInstance("Inc", "inc2"),
    CompositeInstance("Queue", "queue"),
    Inject("int", "inject", 8, "gen_func"),

    Connect("inject", "inc1"),
    Connect("inc1", "queue"),
    Connect("queue", "inc2"),
    APIFunction("dequeue", "queue", "dequeue", "inc2", "out", "int", -1)
)

include = r'''int gen_func(int i) { return i; }'''

g = generate_graph(desugar(p))
#generate_code_and_run(g, "enqueue(1); enqueue(4); enqueue(9); out(dequeue()); out(dequeue()); out(dequeue()); enqueue(0); enqueue(2); out(dequeue()); out(dequeue());", [3, 6, 11, 2, 4])

testing = r'''
run();
for(int i=0; i<8; i++) {
    usleep(1000);
    printf("%d\n", dequeue());
}
finalize();
'''

generate_code_with_test(g, "run(); finalize();", include)
generate_code_and_run(g, testing, None, include)