import graph
import program
from workspace import scope_append, push_scope, pop_scope, get_current_collection
from abc import abstractmethod

####################### Data type ########################

Int = 'int'
Size = 'size_t'
Void = 'void'


def Uint(bits):
    return 'uint%d_t' % bits


def Pointer(x):
    return x + '*'


class Array(object):
    def __init__(self, type, size=None):
        self.type = type
        self.size = size

####################### State ########################


class Field(object):
    def __init__(self, type, value=0, copysize=None, shared=None):
        self.type = type
        self.value = value
        self.copysize = copysize
        self.shared = shared


class Persistent(object):
    def __init__(self, type, value=None):
        self.type = type
        self.value = value


class PerPacket(object):
    def __init__(self, type):
        self.type = type

    def __getattr__(self, item):
        type = self.type
        if item in type.__dict__:
            return item
        else:
            raise Exception("Per-packet state '%s' doesn't have field '%s'." % (type.__name__, item))


class State(object):
    id = 0
    defined = set()

    def __init__(self, name=None, init=[], declare=True, instance=True):
        self.init(*init)
        content, fields, init_code, mapping = self.get_content()

        if self.__class__.__name__ not in State.defined:
            if instance:
                class_init = None
            else:
                class_init = init_code
            scope_append(graph.State(self.__class__.__name__, content, class_init, declare, fields, mapping))
            State.defined.add(self.__class__.__name__)

        if name is None:
            name = self.__class__.__name__ + str(self.__class__.id)
            self.__class__.id += 1
        self.name = name

        if instance:
            scope_append(program.StateInstance(self.__class__.__name__, name, init_code))

    def init(self, *init):
        pass

    def __setattr__(self, key, value):
        if key in self.__class__.__dict__:
            o = self.__getattribute__(key)
            if isinstance(o, Field):
                super(State, self).__setattr__(key, Field(o.type, value))
                return
        super(State, self).__setattr__(key, value)

    def sanitize_init(self, x):
        if isinstance(x, State):
            return x.name
        elif isinstance(x, list):
            return [self.sanitize_init(i) for i in x]
        else:
            return x

    def get_content(self):
        content = ""
        fields = []
        init = []
        mapping = {}
        for s in self.__class__.__dict__:
            o = object.__getattribute__(self, s)
            if isinstance(o, Field):
                fields.append(s)
                init.append(self.sanitize_init(o.value))

                if isinstance(o.type, str):
                    type = o.type
                    content += "%s %s;\n" % (type, s)
                elif isinstance(o.type, Array):
                    mytype = o.type.type
                    if not isinstance(mytype, str):
                        mytype = mytype.__name__
                    type = mytype + '*'
                    if o.type.size is None:
                        size = '[]'
                    elif isinstance(o.type.size, int):
                        size = '[%d]' % o.type.size
                    elif isinstance(o.type.size, list):
                        size = ''
                        for v in o.type.size:
                            size += '[%d]' % v
                    content += "%s %s%s;\n" % (mytype, s, size)
                else:
                    type = o.type.__name__
                    content += "%s %s;\n" % (type, s)

                special = None
                special_val = None
                if o.copysize:
                    special = 'copysize'
                    special_val = o.copysize
                elif o.shared:
                    special = 'shared'
                    special_val = o.shared

                mapping[s] = [type, None, special, special_val]
        return content, fields, init, mapping


class Pipeline(object):
    id = 0
    state = None

    def __init__(self, name=None):
        if name is None:
            name = self.__class__.__name__
            if self.__class__.id > 0:
                name += str(self.__class__.id)
            self.__class__.id += 1
        self.name = name

        assert isinstance(self.state, PerPacket), \
            "Per-packet state %s.state must be set to PerPacket(StateType), but %s is given." % (self.name, self.state)

        push_scope('')
        self.impl()  # TODO: add pipeline state
        self.state = self.state.type(instance=False)
        self.scope = pop_scope()

    @abstractmethod
    def impl(self):
        pass


