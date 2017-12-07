from library import *
from compiler import Compiler

class Compo(Composite):
    def configure(self):
        self.inp = Input(Int)
        self.out = [Output(Int), Output(Int)]

    def spec(self):
        for i in range(2):
            self.inp >> Inc(configure=[Int]) >> self.out[i]

    def impl(self):
        self.inp >> Inc(configure=[Int]) >> self.out[0]
        self.inp >> Inc(configure=[Int]) >> Inc(configure=[Int]) >> self.out[1]

class Display(Element):
    def configure(self):
        self.inp = Input(Int)

    def impl(self):
        self.run_c(r'''printf("%d\n", inp());''')

inc = Inc(configure=[Int])
compo = Compo()
display = Display()

inc >> compo
compo.out[0] >> display
compo.out[1] >> display

t = APIThread("run", [Int], None)
t.run(inc, compo, display)

def run_spec():
    c = Compiler()
    c.desugar_mode = "spec"
    c.testing = "run(0);"
    c.generate_code_and_run([2,2])

def run_impl():
    c = Compiler()
    c.desugar_mode = "impl"
    c.testing = "run(0);"
    c.generate_code_and_run([2,3])

run_spec()
#run_impl()