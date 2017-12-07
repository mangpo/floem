from library import *
from compiler import Compiler


class MyState(State):
    val = Field(Int)


class MyFlow(Flow):
    state = PerPacket(MyState)

    class Save(Element):

        def configure(self):
            self.inp = Input(Int)
            self.out = Output()

        def impl(self):
            state = MyFlow.state
            self.run_c(r'''state.val = inp(); output { out(); }''')
            self.defs(state.val)  # TODO: use this info instead of analyze C

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            state = MyFlow.state
            self.run_c(r'''printf("%d\n", state.val);''')
            self.uses(state.val)

    class Run(CallablePipeline):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            display = MyFlow.Display()
            save = MyFlow.Save()

            self.inp >> save >> display

    def impl(self):
        MyFlow.Run('run')

c = Compiler(MyFlow)
c.testing = r'''
run(1);
run(2);
run(3);
'''
c.generate_code_and_run([1,2,3])


# TODO: pass per-packet state as parameter