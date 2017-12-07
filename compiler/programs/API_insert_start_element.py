from library import *
from compiler import Compiler

class func(API):
    def configure(self):
        self.inp = Input(Int)
        self.offset = Input(Int)
        self.out = Output(Int)

    def args_order(self):
        return [self.inp, self.offset]

    def impl(self):
        inc1 = Inc(name='inc1', configure=[Int])
        inc2 = Inc(name='inc2', configure=[Int])
        add1 = Add(name='add1', configure=[Int])
        add2 = Add(name='add2', configure=[Int])

        self.inp >> inc1 >> add1.inp1
        self.inp >> inc2 >> add1.inp2
        add1 >> add2.inp1
        self.offset >> add2.inp2
        add2 >> self.out

func('func')

c = Compiler()
c.testing = "out(func(1, 0)); out(func(2, 100));"
c.generate_code_and_run([4, 106])