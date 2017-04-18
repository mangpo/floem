from dsl import *
from elements_library import *

inject1 = create_inject_instance("inject1", "int", 10, "gen_func")
inject2 = create_inject_instance("inject2", "int", 10, "gen_func")
Add = create_add("Add", "int")

add = Add()

add(inject1(), inject2())
t = API_thread("run", [], "int")
t.run(add)

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
c.generate_code_and_run([2*i for i in range(10)])