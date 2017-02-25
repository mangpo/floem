from dsl import *
from elements_library import *

inject1 = create_inject_instance("inject1", "int", 10, "gen_func")
inject2 = create_inject_instance("inject2", "int", 10, "gen_func")
Add = create_add("Add", "int")

add = Add()

add(inject1(), inject2())
t = API_thread("run", [], "int")
t.run_start(add)

c = Compiler()
c.include = r'''int gen_func(int i) { return i; }'''
c.testing = r'''
run_threads();
for(int i=0;i<10;i++)
    out(run());
kill_threads();
'''
c.triggers = True
c.generate_code_and_run([2*i for i in range(10)])