from dsl import *


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
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c("")

class Constant(Element):
    def configure(self, c):
        self.out = Output(SizeT)
        self.c = c

    def impl(self):
        self.run_c(r'''
        output { out(%s); }
        ''' % self.c)


class Print(Element):
    def configure(self, data_type=Int):
        self.data_type = data_type
        self.inp = Input(data_type)

    def impl(self):
        if self.data_type in [SizeT, Uintptr]:
            format = "%ld"
        elif self.data_type == Float:
            format = "%f"
        elif self.data_type == Double:
            format = "%lf"
        else:
            format = "%d"

        self.run_c(r'''
        %s x = inp();
        printf("%s\n", x);
        ''' % (self.data_type, format))
