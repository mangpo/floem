from library_dsl2 import *
from compiler import Compiler


class Compo(Composite):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        class Inner(Composite):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.inp >> Inc(configure=[Int]) >> Inc(configure=[Int]) >> self.out

            def spec(self):
                self.inp >> Inc(configure=[Int]) >> self.out

        self.inp >> Inner() >> self.out


test = Compo()
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

#c.desugar_mode = "impl"
#c.generate_code_and_run([3])

# TODO: still buggy