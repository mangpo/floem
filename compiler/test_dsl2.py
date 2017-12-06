from dsl2 import *
import unittest
import os
import queue_smart2
import library_dsl2
from compiler import Compiler

class Nop(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        int x = in();
        output { out(x); }
        ''')

class NopSize(Element):
    def configure(self):
        self.inp = Input(Size)
        self.out = Output(Size)

    def impl(self):
        self.run_c(r'''
        int x = in();
        output { out(x); }
        ''')

class NopPipe(Composite):

    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        a = Nop('a')
        b = Nop('b')
        self.inp >> a >> b >> self.out


class TestDSL2(unittest.TestCase):
    def setUp(self):
        reset()

    def test_run(self):
        tests = ["API_increment1.py",
                 "API_increment2.py",
                 "API_insert_start_element.py",
                 "pipeline_state_simple.py",
                 "pipeline_state_nonempty.py",
                 "queue_owner_bit.py",
                 "queue_variable_size.py",
                 "join_inject.py",
                 "join_inject2.py",
                 "smart_queue_entry.py",
                 "spec_impl.py",
                 "spec_impl_at.py",
                 "probe_spec_impl.py",
                 "probe_multi.py",
                 "nested_compo_in_impl.py",
                 "nested_spec_impl_in_compo.py",
                 "pipeline_state_empty_port1.py",
                 "pipeline_state_empty_port2.py",
                 "pipeline_state_empty_port3.py",
                 ]
        for test in tests:
            status = os.system("cd programs_dsl2; python " + test + "; cd ..")
            self.assertEqual(status, 0, "Error at " + test)

    def test_connection(self):
        a = Nop(name="a")
        b = Nop(name="b")
        c = Nop(name="c")
        a >> b >> c
        a.out >> b.inp
        a >> b.inp
        a.out >> b

        try:
            a.inp >> b
        except TypeError as e:
            self.assertNotEqual(e.message.find("unsupported operand type(s) for >>: 'Input' and 'Nop'"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_connection_compo(self):
        compo1 = NopPipe('compo1')
        compo2 = NopPipe('compo2')
        a = Nop('a')
        b = Nop('b')
        a >> compo1 >> compo2 >> b

        a.out >> compo1 >> compo2.inp
        compo2.out >> b

        a >> compo1.inp
        compo1.out >> compo2 >> b.inp

        a.out >> compo1.inp
        compo1.out >> compo2.inp
        compo2.out >> b.inp

        try:
            compo1.inp >> compo2
        except Exception as e:
            self.assertNotEqual(e.message.find("Illegal to connect"), -1)
        else:
            self.fail('Exception is not raised.')

        try:
            b >> compo1.out
        except Exception as e:
            self.assertNotEqual(e.message.find("Illegal to connect"), -1)
        else:
            self.fail('Exception is not raised.')

        try:
            c = NopSize('c')
            a >> c
        except Exception as e:
            self.assertNotEqual(e.message.find("Illegal to connect port 'out' of element 'a' of type"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_pipeline_state_liveness1(self):
        reset()

        class MyState(State):
            a = Field(Int)

        class Dummy1(Element):
            def impl(self):
                self.run_c(r'''state.a = 0; int x = state.a;''')

        class Dummy2(Element):
            def impl(self):
                self.run_c(r'''int x = state.a; state.a = 0;''')

        class run1(InternalLoop):
            def impl(self):
                Dummy1()

        class run2(InternalLoop):
            def impl(self):
                Dummy2()

        class main(Pipeline):
            state = PerPacket(MyState)

            def impl(self):
                run1('run1')
                run2('run2')

        c = Compiler(main)
        g = c.generate_graph()
        f1 = g.instances["main_run1_Dummy10"]
        self.assertEqual(f1.liveness, set(['a']))  # TODO: more precise, set()
        f2 = g.instances["main_run2_Dummy20"]
        self.assertEqual(f2.liveness, set(['a']))

    def test_pipeline_state_liveness2(self):
        reset()

        class Choose(Element):
            def configure(self):
                self.inp = Input(Int)
                self.out0 = Output()
                self.out1 = Output()

            def impl(self):
                self.run_c(r'''
                int x = in(); 
                state.a = x; 
                state.core = 0; 
                output switch { case (x % 2 == 0): out0(); else: out1(); }''')

        class DefA(ElementOneInOut):
            def impl(self):
                self.run_c(r'''output { out(); }''')

        class DefB(ElementOneInOut):
            def impl(self):
                self.run_c(r'''state.b = 0; output { out(); }''')

        class UseA(ElementOneInOut):
            def impl(self):
                self.run_c(r'''state.c = state.a; output { out(); }''')

        class UseB(ElementOneInOut):
            def impl(self):
                self.run_c(r'''state.c = state.b; output { out(); }''')

        class UseCore(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''state.core = 0;''')

        Enq, Deq, Scan = queue_smart2.smart_queue("queue", 256, 1, 2, overlap=16)

        class run1(API):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                choose = Choose()
                enq = Enq()

                self.inp >> choose
                choose.out0 >> DefA() >> enq.inp[0]
                choose.out1 >> DefB() >> enq.inp[1]

        class run2(API):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                deq = Deq()
                f = UseCore()

                self.inp >> deq
                deq.out[0] >> UseA() >> f
                deq.out[1] >> UseB() >> f

        class MyState(State):
            core = Field(Int)
            a  = Field(Int)
            b = Field(Int)
            c = Field(Int)

        class main(Pipeline):
            state = PerPacket(MyState)

            def impl(self):
                run1('run1')
                run2('run2')

        c = Compiler(main)
        g = c.generate_graph()
        choose = g.instances["main_run1_Choose0"]
        self.assertEqual(choose.uses, set(['a', 'b', 'core']))
        self.assertEqual(choose.liveness, set())
        defb = g.instances["main_run1_DefB0"]
        self.assertEqual(defb.uses, set(['b', 'core']))
        self.assertEqual(defb.liveness, set(['core']))

    def test_connect_ele_compo(self):
        reset()

        def get_element_instance():
            return library_dsl2.Inc(configure=[Int])

        def get_composite_instance():
            class My(Composite):
                def configure(self):
                    self.inp = Input(Int)
                    self.out = Output(Int)

                def impl(self):
                    f1 = library_dsl2.Inc(configure=[Int])
                    f2 = library_dsl2.Inc(configure=[Int])
                    self.inp >> f1 >> f2 >> self.out

            return My()

        class f(API):
            def configure(self):
                self.inp = Input(Int)

            def impl(self):
                e1 = get_element_instance()
                e2 = get_element_instance()
                compo = get_composite_instance()
                self.inp >> e1 >> compo >> e2 >> library_dsl2.Print()

        f('f')

        c = Compiler()
        c.testing = 'f(0);'
        c.generate_code_and_run([4])

