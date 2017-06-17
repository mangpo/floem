from dsl2 import *

class A(State):
    count = Field(Int)

    def init(self, count=0):
        self.count = count


class Counter(Element):
    a = Persistent(A)  # TODO: Persistent

    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def states(self, a):
        self.a = a

    def impl(self):
        self.run_c(r'''
        int x = inp();
        a->count += x;
        output { out(a->count); }
        ''')

a = A(init=[0])


class Shared(API):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        counter = Counter(states=[a])
        self.inp >> counter >> self.out


run1 = Shared('run1')
run2 = Shared('run2')


class Local(API):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        a = A(init=[0])
        counter = Counter(states=[a])
        self.inp >> counter >> self.out

run1 = Local('run3')
run2 = Local('run4')

c = Compiler()
c.testing = r'''
out(run1(2));
out(run2(2));
out(run3(1));
out(run4(1));
'''
c.generate_code_and_run([2,4,1,1])