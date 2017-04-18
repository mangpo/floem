from dsl import *
from elements_library import *

fork = create_fork_instance("fork2", 2, "int")

Chioce = create_element("Choice",
            [Port("in", ["int"])],
            [Port("out1", ["int"]), Port("out2", ["int"])],
            r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')
choice1 = Chioce("choice1")
choice2 = Chioce("choice2")

Inc = create_add1("Inc", "int")
inc1 = Inc("inc1")
inc2 = Inc("inc2")

Add = create_add("Add", "int")
add1 = Add("add1")
add2 = Add("add2")

x1, x2 = fork(None)
y1, y2 = choice1(x1)
z1, z2 = choice2(x2)
add1(y1, z2)
add2(inc1(y2), inc2(z1))

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = r'''
fork2(1);
fork2(2);
fork2(3);
fork2(4);
'''
c.generate_code_and_run()