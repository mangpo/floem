from dsl import *

Storage = create_state("Storage", "int sum;", [0])
Sum = create_element("Sum", [Port("in", ["int"])], [], r'''this->sum += in(); printf("%d\n", this->sum);''',
                     [("Storage", "this")])
s1 = Storage(init=[50])
sum1 = Sum("_sum1", [s1])
s2 = Storage()
sum2 = Sum("_sum2", [s2])

t1 = API_thread("sum1", ["int"], None)
t2 = API_thread("sum2", ["int"], None)
t1.run(sum1)
t2.run(sum2)

c = Compiler()
c.testing = "sum1(1); sum1(2); sum2(0);"
c.generate_code_and_run([51, 53, 0])