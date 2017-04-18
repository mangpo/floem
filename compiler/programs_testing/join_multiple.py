from dsl import *
from elements_library import *

Fork2 = create_fork("Fork2", 2, "int")
Fork3 = create_fork("Fork3", 3, "int")
Forward = create_identity("Forward", "int")
Add = create_add("Add", "int")

f1 = Forward()
f2 = Forward()

x1, x2, x3 = Fork3("fork3")(None)

y1 = f1(x1)
y2, y3 = Fork2()(x2)
y4 = f2(x3)

z1 = Add()(y1, y2)
z2 = Add()(y3, y4)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = "fork3(1);"
c.generate_code_and_run([2,2])