from dsl2 import *

class A(State):
    count = Field(Int)

    def init(self, count=0):
        self.count = count


class Counter(Element):
    a = A

    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def states(self, a):
        self.a = a  # TODO: local: self.a = A() is okay too

    def run(self):
        self.run_c(r'''
        int x = inp();
        a->count += x;
        output { out(a->count); }
        ''')

a = A(init=[0])

class Shared(API):
    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def implementation(self):
        counter = Counter(states=[a])
        self.inp >> counter >> self.out


run1 = Shared('run1')
run2 = Shared('run2')


class Local(API):
    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def implementation(self):
        a = A(init=[0])
        counter = Counter(states=[a])
        self.inp >> counter >> self.out

run1 = Local('run3')
run2 = Local('run4')