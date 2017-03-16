from dsl import *

A = create_element("A",
                   [],
                   [Port("out", [])],
                   r'''printf("1\n"); output { out(); }''')

B = create_element("B",
                   [Port("in", [])],
                   [],
                   r'''in(); printf("2\n");''')
a1 = A("a")
a2 = A("a2")
b1 = B("b")
b2 = B("b2")

b1(a1())
b2(a2())

t = internal_thread("t")
t.run_start(a1, b1, a2, b2)
t.run_order(b1, a2)

c = Compiler()
c.generate_code_and_run()