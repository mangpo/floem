from compiler import *
from standard_elements import *

p = Program(
    Forward,
    InjectAndProbe("int", "inject", "probe", "probe_state", 1, 10),
    Composite("Unit",
              [Port("in", ("f1", "in"))],
              [Port("out", ("f3", "out"))],
              [],
              [],
              Program(
                  ElementInstance("Forward", "f1"),
                  ElementInstance("Forward", "f2"),
                  ElementInstance("Forward", "f3"),
                  Connect("f1", "inject"),
                  Connect("inject", "f2"),
                  Connect("f2", "probe1"),
                  Connect("probe1", "f3"),
              )),
    CompositeInstance("Unit", "u")
)

g = generate_graph(p)
generate_code_and_run(g, r'''
int i;
inject(42);
inject(123);
for (i=0; i < probe_state.p; i++)
printf("%d\n", probe_state.data[i]);''', [42, 123, 42, 123])