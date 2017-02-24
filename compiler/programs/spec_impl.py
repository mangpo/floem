from compiler import *
from desugaring import desugar
from standard_elements import Forward

p = Program(
    Forward,
    ElementInstance("Forward", "f"),
    ElementInstance("Forward", "g"),
    Connect("f", "g"),
    Spec(
        APIFunction("all", ["int"], "int"),
        ResourceMap("all", "f", True),
        ResourceMap("all", "g")
    ),
    Impl(
        APIFunction("write", ["int"], None),
        APIFunction("read", [], "int"),
        ResourceMap("write", "f", True),
        ResourceMap("read", "g", True),
    ),
)


def run_spec():
    dp = desugar(p, mode="spec")
    g = generate_graph(dp)
    generate_code_and_run(g, "out(all(42)); out(all(123)); out(all(999));", [42,123,999])


def run_impl():
    dp = desugar(p, mode="impl")
    g = generate_graph(dp)
    generate_code_and_run(g, "write(42); out(read()); write(123); out(read()); write(999); out(read());", [42,123,999])

run_spec()
run_impl()