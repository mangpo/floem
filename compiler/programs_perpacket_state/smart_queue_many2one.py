from dsl import *
import queue_smart
from compiler import Compiler

class MyState(State):
    a = Field(Int)
    a0 = Field(Int)
    b0 = Field(Int)
    qid = Field(Int)


class Save(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''state.a = inp(); state.qid = 0; output { out(); }''')

class Classify(Element):
    def configure(self):
        self.inp = Input()
        self.out1 = Output()
        self.out2 = Output()

    def impl(self):
        self.run_c(r'''
    output switch {
        case (state.a % 2) == 0: out1();
        else: out2(); }
    ''')

class A0(ElementOneInOut):
    def impl(self):
        self.run_c(r'''state.a0 = state.a + 100; output { out(); }''')


class B0(ElementOneInOut):
    def impl(self):
        self.run_c(r'''state.b0 = state.a * 2; output { out(); }''')

class A1(Element):
    def configure(self):
        self.inp  = Input()

    def impl(self):
        self.run_c(r'''printf("a1 %d\n", state.a0);''')

class B1(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''printf("b1 %d\n", state.b0);''')

class Print(Element):
    def configure(self, x):
        self.inp = Input()
        self.x = x

    def impl(self):
        self.run_c(r'''printf("clean %s!\n");''' % self.x)

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        Enq, Deq, Clean = queue_smart.smart_queue("queue", 32, 1, 1, 2, clean=True)

        class run1(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                save = Save()
                classify = Classify()
                enq = Enq()

                self.inp >> save >> classify
                classify.out1 >> A0() >> enq.inp[0]
                classify.out2 >> B0() >> enq.inp[1]

                clean = Clean()

                clean.out[0] >> Print(configure='a')
                clean.out[1] >> Print(configure='b')


        class run2(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                deq = Deq()

                self.inp >> deq
                deq.out[0] >> A1()
                deq.out[1] >> B1()

        run1('run1')
        run2('run2')


c = Compiler(main)
c.testing = "run1(123); run2(0); run1(42);  run2(0);"
c.generate_code_and_run(['b1', 246, 'clean', 'b!', 'a1', 142])
