from abc import ABCMeta, abstractmethod
import graph
import program



class Element(object):

    def __init__(self, name=None, params=[]):
        self.code = ''
        self.init(*params)
        self.port()
        self.run()

        inports = []
        outports = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Input):
                inports.append(graph.Port(s, o.args))
            elif isinstance(o, Output):
                outports.append(graph.Port(s, o.args))
        e = graph.Element(self.__class__.__name__, inports, outports, self.code)

        self.id = 0
        if name is None:
            name = self.__class__.__name__ + str(self.id)
            self.id += 1
        inst = program.ElementInstance(self.__class__.__name__, name)

        print inst  # TODO: add to scope


    def init(self, *params):
        pass

    @abstractmethod
    def port(self):
        pass

    @abstractmethod
    def run(self):
        pass

    def run_c_element(self, code):
        self.code = code


class Port(object):
    def __init__(self, *args):
        self.args = args


class Input(Port):
    pass


class Output(Port):
    pass


class Field(object):

    def __init__(self, type, value=None):
        self.type = type
        self.value = value


Int = 'int'
Size = 'size_t'


def Uint(bits):
    return 'uint%d_t' % bits


#########################################




class Add(Element):

    def port(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def run(self):
        self.run_c_element(r'''
        int x = in();
        output { out(x); }
        ''')


add = Add(name="add")