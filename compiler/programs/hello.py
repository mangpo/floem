from floem import *

class Hello(Element):
    def impl(self):
        self.run_c(r'''printf("hello world\n");''')


class P(Pipeline):
    def impl(self):
        Hello()

P('p')

c = Compiler()
c.testing = "while(1) pause();"
c.generate_code_and_run()