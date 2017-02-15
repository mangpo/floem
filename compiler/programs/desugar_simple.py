from compiler import *
from desugaring import desugar
from standard_elements import Forward

p = Program(
    Forward,
    ElementInstance("Forward", "f[4]"),
    ElementInstance("Forward", "g[4]"),
    Connect("f[i]", "g[i]"),
    APIFunction("id[i]", "f[i]", "in", "g[i]", "out", "int")
)
p = desugar(p)
g = generate_graph(p, True)
generate_code_and_run(g, "out(id0(42)); out(id0(123)); out(id3(999));", [42,123,999])