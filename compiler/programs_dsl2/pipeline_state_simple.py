from library_dsl2 import *
from compiler import Compiler


class MyState(State):
    val = Field(Int)


class MyPipeline(Pipeline):
    state = PerPacket(MyState)

    class Save(Element):

        def configure(self):
            self.inp = Input(Int)
            self.out = Output()

        def impl(self):
            state = MyPipeline.state
            self.run_c(r'''state.val = inp(); output { out(); }''')
            self.defs(state.val)  # TODO: use this info instead of analyze C

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            state = MyPipeline.state
            self.run_c(r'''printf("%d\n", state.val);''')
            self.uses(state.val)

    class Run(API):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            display = MyPipeline.Display()
            save = MyPipeline.Save()

            self.inp >> save >> display

    def impl(self):
        MyPipeline.Run('run')

c = Compiler(MyPipeline)
c.testing = r'''
run(1);
run(2);
run(3);
'''
c.generate_code_and_run([1,2,3])


# TODO: pass per-packet state as parameter