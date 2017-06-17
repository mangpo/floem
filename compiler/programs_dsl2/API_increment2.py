from library_dsl2 import *

class add2(API):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        inc1 = Inc('inc1', configure=[Int])
        inc2 = Inc('inc2', configure=[Int])
        self.inp >> inc1 >> inc2 >> self.out

add2('add2')

c = Compiler()
c.testing = "out(add2(11)); out(add2(0));"
c.generate_code_and_run([13,2])

