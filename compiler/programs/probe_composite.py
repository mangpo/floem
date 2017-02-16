from compiler import *
from standard_elements import *
from desugaring import desugar

p = Program(
    Forward,
    Inject("int", "inject", 10, "gen_func"),
    Probe("int", "probe[2]", 10, "cmp_func"),
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
                  Connect("f2", "probe[0]"),
                  Connect("probe[0]", "f3"),
              )),
    CompositeInstance("Unit", "u")
)

include = r'''
int gen_func(int i) { return i; }
'''

dp = desugar(p)
g = generate_graph(dp)
generate_code_with_test(g, None, include)