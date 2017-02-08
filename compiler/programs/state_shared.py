from compiler import *

p = Program(
    State("Shared", "int sum;", "100"),
    Element("Sum",
            [Port("in", ["int"])],
            [],
            r'''this.sum += in(); printf("%d\n", this.sum);''',
            None,
            [("Shared", "this")]),
    StateInstance("Shared", "s"),
    ElementInstance("Sum", "sum1", ["s"]),
    ElementInstance("Sum", "sum2", ["s"])
)

g = generate_graph(p)
generate_code_and_run(g, "sum1(1); sum1(2); sum2(0);", [101, 103, 103])