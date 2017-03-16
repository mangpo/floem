from dsl import *

Sum = create_element("Sum",
            [Port("in", ["int"])],
            [],
            r'''this.sum += in(); printf("%d\n", this.sum);''',
            State("this", "int sum;", "100"))  # Local state. Init: this.sum = 100

s1 = Sum()
s2 = Sum()

t1 = API_thread("sum1", ["int"], None)
t2 = API_thread("sum2", ["int"], None)
t1.run_start(s1)
t2.run_start(s2)

c = Compiler()
c.testing = "sum1(1); sum1(2); sum2(0);"
c.generate_code_and_run([101, 103, 100])