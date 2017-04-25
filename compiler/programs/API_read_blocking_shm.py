from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
f1 = Forward()
f2 = Forward()

x = f2(f1(None))


t1 = API_thread("put", ["int"], None)
t2 = API_thread("get", [], "int")
t1.run(f1)
t2.run(f2)

CPU_process("put", t1)
CPU_process("get", t2)

c = Compiler()
c.include = r'''
#include "../shm.h"
'''
c.generate_code_and_compile()