from dsl import *
from elements_library import *

Gen = create_element("Gen",
            [],
            [Port("out", ["int"])],
            r'''output { out(3); }''')

Print = create_element("Print",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n",in());''')

gen = Gen()
p = Print()

x = p(gen())

t1 = internal_thread("t1")
t2 = internal_thread("t2")
t1.run(gen)
t2.run(p)

CPU_process("p1", t1)
CPU_process("p2", t2)
master_process("p1")

c = Compiler()
c.include = r'''
#include "../shm.h"
'''
c.testing = "while(true);\n"
#c.testing = "usleep(1000000);\n"
c.generate_code_and_run()