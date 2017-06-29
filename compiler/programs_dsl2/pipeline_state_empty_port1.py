from dsl2 import *
from compiler import Compiler


class Gen(Element):
    def configure(self):
        self.out = Output(Int, Int)

    def impl(self):
        self.run_c(r'''
            for(int i=0; i<10; i++) {
                out(i, 2*i);
            }
            output multiple;
        ''')


class Display(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''
        printf("1\n");
        ''')

class run(API):
    def impl(self):
        Gen() >> Display()

run('run')

c = Compiler()
c.testing = r'''
run();
'''
c.generate_code_and_run([1 for x in range(10)])