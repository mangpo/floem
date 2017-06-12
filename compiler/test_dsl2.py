from dsl2 import *
import unittest


class Nop(Element):
    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def run(self):
        self.run_c(r'''
        int x = in();
        output { out(x); }
        ''')

class NopFloat(Element):
    def port(self):
        self.inp = Input(Size)
        self.out = Output(Size)

    def run(self):
        self.run_c(r'''
        int x = in();
        output { out(x); }
        ''')

class NopPipe(Composite):

    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def implementation(self):
        a = Nop('a')
        b = Nop('b')
        self.inp >> a >> b >> self.out

class TestDSL(unittest.TestCase):
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
            c = NopFloat('c')
            a >> c
        except Exception as e:
            self.assertNotEqual(e.message.find("Illegal to connect port 'out' of element 'a' of type ('int',)"), -1)
        else:
            self.fail('Exception is not raised.')
