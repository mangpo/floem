from dsl import *
from compiler import Compiler

class MyState(State):
    a = Field(Int)

class Gen(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output()

    def impl(self):
        self.run_c("state.a = inp(); output { out(); }")


class Display(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''printf("%d\n", state.a);''')

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        gen = Gen()
        display = Display()

        gen >> display

        put = APIThread('put', ["int"], None)
        put.run(gen)

        get = APIThread('get', [], None)
        get.run(display)

c = Compiler(main)
c.testing = "put(42); get(); put(123); get();"
c.generate_code_and_run([42,123])