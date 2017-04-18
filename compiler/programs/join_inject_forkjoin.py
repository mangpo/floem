from dsl import *
from elements_library import *

inject1 = create_inject_instance("inject1", "int", 10, "gen_func")
inject2 = create_inject_instance("inject2", "int", 10, "gen_func")
Add = create_add("Add", "int")
Fork = create_fork("Fork", 2, "int")
Forward = create_identity("Forward", "int")

add1 = Add()
fork = Fork()
f1 = Forward()
f2 = Forward()
add2 = Add()

x = add1(inject1(), inject2())
x1, x2 = fork(x)
add2(f1(x1), f2(x2))

t = API_thread("run", [], "int")
t.run(add1, fork, f1, f2, add2)

t1 = internal_thread("t1")
t1.run(inject1)

t2 = internal_thread("t2")
t2.run(inject2)

c = Compiler()
c.include = r'''int gen_func(int i) { return i; }'''
c.testing = r'''
for(int i=0;i<10;i++)
    out(run());
'''
c.generate_code_and_run([4*i for i in range(10)])