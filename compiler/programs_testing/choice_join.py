from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Drop = create_drop("Drop", "int")
Choice = create_element("Choice", [Port("in", ["int"])], [Port("out1", ["int"]), Port("out2", ["int"])],
                        r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')
Add = create_add("Add", "int")


choice = Choice("choice")
fork = create_fork_instance("fork3", 3, "int")
drop1 = Drop()
drop2 = Drop()
f = Forward()
add = Add("add")

c1, c2 = choice(None)
x1, x2, x3 = fork(c1)
drop1(x3)
x1 = f(x1)
out = add(x1, x2)

drop2(c2)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = r'''
choice(2);
choice(3);
choice(4);
choice(5);
'''

c.generate_code_and_run([4,8])
