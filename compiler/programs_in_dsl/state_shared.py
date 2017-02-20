from dsl import *

Storage = create_state("Storage", "int sum;", [0])
Sum = create_element("Sum",
            [Port("in", ["int"])],
            [],
            r'''this.sum += in(); printf("%d\n", this.sum);''',
            None,
            [("Storage", "this")])
s = Storage(init=[50])
sum1 = Sum("sum1", [s])
sum2 = Sum("sum2", [s])

c = Compiler()
c.testing = "sum1(1); sum1(2); sum2(0);"
c.generate_code_and_run([51, 53, 53])