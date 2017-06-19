from dsl2 import *
import unittest
import os


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
    def test_run(self):
        tests = ["API_increment1.py",
                 "API_increment2.py",
                 "API_insert_start_element.py",
                 "pipeline_state_simple.py",
                 "queue_owner_bit.py",
                 ]
        for test in tests:
            status = os.system("cd programs_dsl2; python " + test + "; cd ..")
            self.assertEqual(status, 0, "Error at " + test)

    def test_connection(self):
        reset()

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
