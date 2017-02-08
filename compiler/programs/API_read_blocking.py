from compiler import *
from thread_allocation import *
from standard_elements import *

p = Program(
    Forward,
    ElementInstance("Forward", "f1"),
    ElementInstance("Forward", "f2"),
    Connect("f1", "f2"),
    APIFunction("put", "f1", "in", "f1", None, None),
    APIFunction("get", "f2", None, "f2", "out", "int")
)

g = generate_graph(p)
generate_code_and_run(g, "put(42); out(get()); put(123); out(get());", [42,123])
