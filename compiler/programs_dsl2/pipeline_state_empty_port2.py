from dsl2 import *
from compiler import Compiler

class MyState(State):
    b = Field(Int)


class main(Pipeline):
    state = PerPacket(MyState)

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

    class Save(Element):
        def configure(self):
            self.inp = Input(Int, Int)
            self.out = Output(Int)

        def impl(self):
            self.run_c(r'''
            (int a, int b) = inp();
            state.b = b;
            output { out(a); }
            ''')

    class Get(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(Int)

        def impl(self):
            self.run_c(r'''
            int b = state.b;
            output { out(b); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d\n", state.b);
            ''')

    class run(API):
        def impl(self):
            main.Gen() >> main.Save() >> main.Get() >> main.Display()

    def impl(self):
        main.run('run')

c = Compiler(main)
c.testing = r'''
run();
'''
c.generate_code_and_run([2*x for x in range(10)])