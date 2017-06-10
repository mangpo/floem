from abc import ABCMeta, abstractmethod
import graph
import program

scope = [[]]

def scope_append(x):
    scope[-1].append(x)


class Element(object):
    defined = set()

    def __init__(self, name=None, params=[]):
        self.name = name
        self.code = ''
        self.init(*params)
        self.port()
        self.run()

        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Port):
                o.name = s

        unique = self.__class__.__name__ + "_".join([str(p) for p in params])
        if unique not in Element.defined:
            inports = []
            outports = []
            for s in self.__dict__:
                o = self.__dict__[s]
                if isinstance(o, Input):
                    inports.append(graph.Port(s, o.args))
                elif isinstance(o, Output):
                    outports.append(graph.Port(s, o.args))
            e = graph.Element(unique, inports, outports, self.code)
            scope_append(e)

        self.id = 0
        if name is None:
            name = self.__class__.__name__ + str(self.id)
            self.id += 1
        inst = program.ElementInstance(unique, name)
        scope_append(inst)

    def init(self, *params):
        pass

    @abstractmethod
    def port(self):
        pass

    @abstractmethod
    def run(self):
        pass

    def run_c(self, code):
        self.code = code

    def run_c_element(self, name):
        raise Exception("Unimplemented")

    def run_c_function(self, name):
        raise Exception("Unimplemented")

    def __getattribute__(self, item):
        x = object.__getattribute__(self, item)
        if isinstance(x, Port):
            x.element = self
        return x

    def __rshift__(self, other):
        if isinstance(other, Element):
            c = program.Connect(self.name, other.name)
        elif isinstance(other, Input):
            c = program.Connect(self.name, other.element.name, None, other.name)
        else:
            raise Exception("Attempt to connect element '%s' to '%s', which is not an element or input port." %
                            (self.name, other))
        scope_append(c)
        return other


class Port(object):
    def __init__(self, *args):
        self.name = None
        self.element = None
        self.args = args


class Input(Port):
    pass

class Output(Port):
    def __rshift__(self, other):
        if isinstance(other, Element):
            c = program.Connect(self.element.name, other.name, self.name)
        elif isinstance(other, Input):
            c = program.Connect(self.element.name, other.element.name, self.name, other.name)
        else:
            raise Exception("Attempt to connect element '%s' to '%s', which is not an element or input port." %
                            (self.element.name, other))
        scope_append(c)
        return other


class Field(object):

    def __init__(self, type, value=None):
        self.type = type
        self.value = value


Int = 'int'
Size = 'size_t'


def Uint(bits):
    return 'uint%d_t' % bits


#########################################


class Nop(Element):

    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def run(self):
        self.run_c(r'''
        int x = in();
        output { out(x); }
        ''')


a = Nop(name="a")
b = Nop(name="b")
c = Nop(name="c")
a >> b >> c
a.out >> b.inp
a >> b.inp
a.out >> b

a.inp >> b
print