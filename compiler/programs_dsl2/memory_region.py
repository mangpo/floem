from dsl2 import *
from compiler import Compiler

MemoryRegion("region", 10)

class Test(Element):
    def impl(self):
        self.run_c(r'''
int* p = (int*) region;
*p = 99;
printf("%d\n", *p);
        ''')

Test('test')

c = Compiler()
c.resource = False
c.remove_unused = False
c.include = r'''
#include "../shm.h"
'''
c.testing = r'''
test();
'''
c.generate_code_and_run([99])