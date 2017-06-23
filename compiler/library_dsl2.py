from dsl2 import *


class Identity(Element):

    def configure(self, data_type):
        self.data_type = data_type
        self.inp = Input(self.data_type)
        self.out = Output(self.data_type)

    def impl(self):
        self.run_c(r'''
        %s x = inp();
        output { out(x); }
        ''' % self.data_type)


class Inc(Element):
    def configure(self, data_type):
        self.data_type = data_type
        self.inp = Input(data_type)
        self.out = Output(data_type)

    def impl(self):
        self.run_c(r'''
        %s x = inp();
        output { out(x + 1); }
        ''' % self.data_type)


class Add(Element):
    def configure(self, data_type):
        self.data_type = data_type
        self.inp1 = Input(self.data_type)
        self.inp2 = Input(self.data_type)
        self.out = Output(self.data_type)

    def impl(self):
        self.run_c(r'''
        %s x1 = inp1();
        %s x2 = inp2();
        output { out(x1 + x2); }
        ''' % (self.data_type, self.data_type))


class Drop(Element):
    def configure(self, data_type):
        self.data_type = data_type
        self.inp = Input(data_type)

    def impl(self):
        self.run_c("")