from floem import *


class Inc(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        self.run_c("int x = inp() + 1; output { out(x); }")


class inc2(CallableSegment):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        self.inp >> Inc() >> Inc() >> self.out


inc2('inc2', process='simple_math')

c = Compiler()
c.generate_code_as_header('simple_math')
c.depend = ['simple_math']
c.compile_and_run('simple_math_ext')