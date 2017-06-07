from dsl import *

create_memory_region("region", 10)

Test = create_element("Test", [], [], r'''
int* p = (int*) region;
*p = 99;
printf("%d\n", *p);
''')

test = Test("test")

c = Compiler()
c.resource = False
c.remove_unused = False
c.include = r'''
#include "../shm.h"
'''
c.testing = r'''
test();
'''
c.generate_code_and_run()
