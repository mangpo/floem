import graph
import program
from workspace import scope_append

####################### Data type ########################

Int = 'int'
Size = 'size_t'


def Uint(bits):
    return 'uint%d_t' % bits

####################### State ########################

class Field(object):
    def __init__(self, type, value=0):
        self.type = type
        self.value = value


class State(object):
    id = 0
    defined = set()

    def __init__(self, name=None, init=[], declare=True):
        self.init(*init)

        if self.__class__.__name__ not in State.defined:
            content, init_code = self.get_content()
            scope_append(graph.State(self.__class__.__name__, content, init_code, declare))
            State.defined.add(self.__class__.__name__)

        if name is None:
            name = self.__class__.__name__ + str(self.__class__.id)
            self.__class__.id += 1
        self.name = name

        scope_append(program.StateInstance(self.__class__.__name__, name))

    def init(self, *init):
        pass

    def __setattr__(self, key, value):
        if key in self.__class__.__dict__:
            o = self.__getattribute__(key)
            if isinstance(o, Field):
                super(State, self).__setattr__(key, Field(o.type, value))
                return
        super(State, self).__setattr__(key, value)

    def get_content(self):
        content = ""
        init = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Field):
                content += "%s %s;\n" % (o.type, s)
                init.append(o.value)
        return content, init
