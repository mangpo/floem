from dsl import *

Sum = create_element("Sum",
            [Port("in", ["int"])],
            [],
            r'''this.sum += in(); printf("%d\n", this.sum);''',
            State("this", "int sum;", "100"))

s1 = Sum("sum1")
s2 = Sum("sum2")

c = Compiler()
c.testing = "sum1(1); sum1(2); sum2(0);"
c.generate_code_and_run([101, 103, 100])