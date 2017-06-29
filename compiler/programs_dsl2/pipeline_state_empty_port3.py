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
            self.out0 = Output(Int)
            self.out1 = Output(Int)

        def impl(self):
            self.run_c(r'''
            (int a, int b) = inp();
            state.b = b;
            output switch { case (a%2==0): out0(a); else: out1(a); }
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
            save = main.Save()
            display = main.Display()
            main.Gen() >> save
            save.out0 >> display
            save.out1 >> display

    def impl(self):
        main.run('run')

c = Compiler(main)
c.testing = r'''
run();
'''
c.generate_code_and_run([2*x for x in range(10)])