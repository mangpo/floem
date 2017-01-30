from compiler import *

p = Program(
    Element("Sum",
            [Port("in", ["int"])],
            [],
            r'''this.sum += in(); printf("%d\n", this.sum);''',
            State("this", "int sum;", "100")),
    ElementInstance("Sum", "sum1"),
    ElementInstance("Sum", "sum2")
)

g = generate_graph(p)
print g
generate_code(g)
