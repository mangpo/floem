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
generate_code(g)
generate_code_and_run(g, "sum1(1); sum1(2); sum2(0);", [101, 103, 100])
