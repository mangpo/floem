from compiler import *
from standard_elements import *

p = Program(
    Forward,
    ElementInstance("Forward", "f1"),
    ElementInstance("Forward", "f2"),
    ElementInstance("Forward", "f3"),
    InjectAndProbe("int", "inject", "probe", "probe_state", 1, 10),
    Connect("f1", "inject"),
    Connect("inject", "f2"),
    Connect("f2", "probe1"),
    Connect("probe1", "f3"),
    APIFunction("read", "f2", None, "f3", "out", "int")
)

g = generate_graph(p)
generate_code_and_run(g, r'''
int i;
inject(42);
printf("%d\n",read());
inject(123);
printf("%d\n",read());
for (i=0; i < probe_state.p; i++)
printf("%d\n", probe_state.data[i]);''', [42, 123, 42, 123])