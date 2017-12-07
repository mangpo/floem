from dsl import *
from compiler import Compiler
import target

class Hello(Element):
    def impl(self):
        self.run_c('''
        printf("hello world\\n");
        sleep(3);
        ''')


class run(Pipeline):
    def impl(self):
        Hello()

def cavium():
    run('run', device=target.CAVIUM, cores=[0])
    c = Compiler()
    c.testing = "sleep(10);"
    c.generate_code_as_header()

def cpu():
    run('run')
    c = Compiler()
    c.testing = "sleep(10);"
    c.generate_code_and_run()

cavium()

