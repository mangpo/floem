from library import *
from compiler import Compiler

Inject = create_inject("inject", "int", 40, "gen_func")

add = Add(configure=[Int])
inject1 = Inject()
inject2 = Inject()

inject1 >> add.inp1
inject2 >> add.inp2

t = APIThread("run", [], "int")
t.run(add)

t1 = InternalThread("t1")
t1.run(inject1)

t2 = InternalThread("t2")
t2.run(inject2)

c = Compiler()
c.include = r'''int gen_func(int i) { return i; }'''
c.testing = r'''
for(int i=0;i<10;i++)
    out(run());
'''
c.generate_code_and_run()