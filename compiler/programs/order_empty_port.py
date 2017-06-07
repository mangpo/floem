from dsl import *

A = create_element("A", [], [Port("out", [])], r'''printf("1\n"); output { out(); }''')

B = create_element("B", [Port("in", [])], [], r'''in(); printf("2\n");''')

C = create_element("C", [], [Port("out", [])], r'''printf("3\n"); output { out(); }''')

D = create_element("D", [Port("in", [])], [], r'''in(); printf("4\n");''')
a = A()
b = B()
c = C()
d = D()

b(a())
d(c())

t = internal_thread("t")
t.run(a,b,c,d)
t.run_order(b,c)

c = Compiler()
c.testing = r'''
usleep(1);
'''
c.generate_code_and_run()