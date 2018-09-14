from floem import *

class Hello(Element):
    def impl(self):
        self.run_c(r'''print_hello();''')


class P(Segment):
    def impl(self):
        Hello()

P('p')

c = Compiler()
c.include = r'''
#include "hello.h"
'''
c.testing = "while(1) pause();"
c.depend = ['hello']
c.generate_code_and_run()