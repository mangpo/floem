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
print g
generate_code(g)
