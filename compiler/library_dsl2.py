from dsl2 import *


class Identity(Element):

    def init(self, data_type):
        self.data_type = data_type

    def port(self):
        self.inp = Input(self.data_type)
        self.out = Output(self.data_type)

    def run(self):
        self.run_c(r'''
        %s x = inp();
        output { out(x); }
        ''' % self.data_type)


class Inc(Element):
    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def run(self):
        self.run_c(r'''
        int x = inp();
        output { out(x + 1); }
        ''')


class Add(Element):
    def init(self, data_type):
        self.data_type = data_type

    def port(self):
        self.inp1 = Input(self.data_type)
        self.inp2 = Input(self.data_type)
        self.out = Output(self.data_type)

    def run(self):
        self.run_c(r'''
        int x1 = inp1();
        int x2 = inp2();
        output { out(x1 + x2); }
        ''')

