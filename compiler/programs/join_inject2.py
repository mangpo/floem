from dsl import *
from elements_library import *

Inject = create_inject("Inject", "int", 40, "gen_func")
inject1 = Inject()
inject2 = Inject()
Add = create_add("Add", "int")

add = Add()

add(inject1(), inject2())
t = API_thread("run", [], "int")
t.run(add)

c = Compiler()
c.include = r'''int gen_func(int i) { return i; }'''
c.testing = r'''
for(int i=0;i<10;i++)
    out(run());
'''
c.generate_code_and_run()