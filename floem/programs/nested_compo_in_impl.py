from library import *
from compiler import Compiler


class Test(Composite):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def spec(self):
        self.inp >> Inc(configure=[Int]) >> self.out

    def impl(self):
        class compo(Composite):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.inp >> Inc(configure=[Int]) >> Inc(configure=[Int]) >> self.out

        self.inp >> compo() >> self.out

test = Test()
f = Inc(configure=[Int])
f >> test

t = APIThread("run", ["int"], "int")
t.run(f, test)

assert len(test.collection.spec) == 1
assert len(test.collection.impl) == 2

c = Compiler()
c.testing = "out(run(0));"

c.desugar_mode = "spec"
c.generate_code_and_run([2])

c.desugar_mode = "impl"
c.generate_code_and_run([3])
