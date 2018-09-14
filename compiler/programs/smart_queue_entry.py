import queue_smart
from dsl import *
from compiler import Compiler

class MyState(State):
    a = Field(Int)
    a0 = Field(Int)
    b0 = Field(Int)
    qid = Field(Int)

class main(Flow):
    state = PerPacket(MyState)

    class Save(Element):
        def configure(self):
            self.inp = Input(Int)
            self.out = Output()

        def impl(self):
            self.run_c(r'''
            state.a = inp();
            state.qid = 0;
            output { out(); }
            ''')

    class Classify(Element):
        def configure(self):
            self.inp = Input()
            self.out = [Output(), Output()]

        def impl(self):
            self.run_c(r'''
            output switch {
                case (state.a % 2) == 0: out0();
                else: out1(); }
            ''')

    class A0(Element):
        def configure(self): self.inp = Input(); self.out = Output()
        def impl(self): self.run_c(r'''state.a0 = state.a + 100; output { out(); }''')

    class B0(Element):
        def configure(self): self.inp = Input(); self.out = Output()
        def impl(self): self.run_c(r'''state.b0 = state.a * 2; output { out(); }''')

    class A1(Element):
        def configure(self): self.inp = Input()
        def impl(self): self.run_c(r'''printf("a1 %d\n", state.a0);''')

    class B1(Element):
        def configure(self): self.inp = Input()
        def impl(self): self.run_c(r'''printf("b1 %d\n", state.b0);''')

    class Clean(Element):
        def configure(self, letter): self.inp = Input(); self.letter = letter
        def impl(self): self.run_c(r'''printf("clean %s!\n");''' % self.letter)

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''printf("done %d\n", state.a);''')

    Enq, Deq, Scan = queue_smart.smart_queue("queue", entry_size=32, size=3, insts=2, channels=2, clean=True,
                                             enq_output=True)

    class run1(CallableSegment):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            classify = main.Classify()
            enq = main.Enq()

            self.inp >> main.Save() >> classify
            classify.out[0] >> main.A0() >> enq.inp[0]
            classify.out[1] >> main.B0() >> enq.inp[1]
            enq.done >> main.Display()

            scan = main.Scan()
            scan.out[0] >> main.Clean(configure=['a'])
            scan.out[1] >> main.Clean(configure=['b'])

    class run2(CallableSegment):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            deq = main.Deq()

            self.inp >> deq
            deq.out[0] >> main.A1()
            deq.out[1] >> main.B1()

    def impl(self):
        main.run1('run1')
        main.run2('run2')


c = Compiler(main)
c.testing = "run1(123); run1(42); run2(0); run2(0); run1(1); run1(2);"
#c.generate_code_and_run(['done', 123, 'done', 42, 'b1', 246, 'a1', 142, 'clean', 'b!', 'clean', 'a!', 'done', '1', 'done', '2'])
c.generate_code_and_run(['done', 123, 'done', 42, 'b1', 246, 'a1', 142, 'done', '1', 'clean', 'b!', 'clean', 'a!', 'done', '2'])