from dsl import *
from elements_library import *

fork = create_fork_instance("fork2", 2, "int")

Chioce = create_element("Choice",
            [Port("in", ["int"])],
            [Port("out1", ["int"]), Port("out2", ["int"])],
            r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')
choice1 = Chioce()
choice2 = Chioce()

Inc = create_add1("Inc", "int")
inc1 = Inc()
inc2 = Inc()

Add = create_add("Add", "int")
add = Add()

x1, x2 = fork(None)
y1, y2 = choice1(x1)
z1, z2 = choice2(x2)
add(y1, z1)
add(inc1(y2), inc2(z2))

c = Compiler()
c.testing = r'''
fork2(1);
fork2(2);
fork2(3);
fork2(4);
'''
c.generate_code_and_run([4,4,8,8])