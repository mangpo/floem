from dsl import *
import queue_smart
from compiler import Compiler

class MyState(State):
    x = Field(Int)
    qid = Field(Int)


class save(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output()

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        state.x = x;
        state.qid = 0;
        output { out(); }
        ''')

class Display(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''
        printf("%d\n", state.x);
        ''')

class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        Enq, Deq, Clean = queue_smart.smart_queue("queue", 32, 16, 1, 1)

        class func1(CallablePipeline):
            def configure(self):
                self.inp = Input()

            def impl(self):
                enq = Enq()
                self.inp >> save() >> enq.inp[0]

        class func2(CallablePipeline):
            def configure(self):
                self.inp = Input()

            def impl(self):
                enq = Enq()
                self.inp >> save() >> enq.inp[0]

        class dequeue(CallablePipeline):
            def configure(self):
                self.inp = Input()

            def impl(self):
                deq = Deq()
                self.inp >> deq >> Display()

        func1('func1')
        func2('func2')
        dequeue('deq')

c = Compiler(main)
c.testing = "func1(1); func2(2); func2(3); func1(4); deq(0); deq(0); deq(0); deq(0);"
c.generate_code_and_run([1,2,3,4])