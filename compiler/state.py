import graph
import program
from workspace import scope_append, decl_append, push_scope, pop_scope, push_decl, pop_decl
from abc import abstractmethod

####################### Data type ########################

Bool = 'bool'
Int = 'int'
Size = 'size_t'
Void = 'void'

def Uint(bits):
    return 'uint%d_t' % bits


def Pointer(x):
    define_state(x)
    return string_type(x) + '*'


class Array(object):
    def __init__(self, type, size=None):
        define_state(type)
        self.type = string_type(type)
        self.size = size


def string_type(x):
    if isinstance(x, str):
        return x
    elif isinstance(x, Array):
        return x
    else:
        return x.__name__


####################### Memory Region ########################

class MemoryRegion(object):
    def __init__(self, name, size):
        self.name = name
        self.size = size

        scope_append(program.MemoryRegion(name, size))

####################### State ########################

def define_state(x):
    if isinstance(x, type) and x.__name__ not in State.all_defined:
        x(instance=False)


class Field(object):
    def __init__(self, t, value=None, copysize=None, shared=None):
        self.value = value
        self.copysize = copysize
        self.shared = shared

        define_state(t)
        self.type = string_type(t)


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
    all_defined = set()
    class_id = 0
    defined = False
    obj_id = 0
    layout = None

    def __init__(self, name=None, init=[], declare=True, instance=True):
        if name is None:
            name = self.__class__.__name__ + str(self.__class__.obj_id)
            self.__class__.obj_id += 1
        self.name = name
        self.declare = declare

        self.compute_layout()
        self.init(*init)
        content, fields, init_code, mapping = self.get_content()

        if not self.__class__.defined:  # belong to subclass
            self.__class__.defined = True
            if instance:
                class_init = None
            else:
                class_init = init_code

            # if the state has the same name as one declared before
            if self.__class__.__name__ in State.all_defined:
                self.__class__.__name__ += str(State.class_id)
                State.class_id += 1
            State.all_defined.add(self.__class__.__name__)
            decl_append(graph.State(self.__class__.__name__, content, class_init, self.declare, fields, mapping))

        if instance:
            scope_append(program.StateInstance(self.__class__.__name__, name, init_code))

    def init(self, *init):
        pass

    def compute_layout(self):
        layout = []
        if self.layout:
            for key in self.__class__.__dict__:
                o = self.__getattribute__(key)
                if isinstance(o, Field):
                    assert o in self.layout, "Layout of state '%s' does not contain field '%s'." % (self.name, key)

            for f in self.layout:
                for key in self.__class__.__dict__:
                    o = self.__getattribute__(key)
                    if f == o:
                        layout.append(key)
                        break

        self.layout = layout

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
        if self.layout:
            layout = self.layout
        else:
            layout = []
            for s in self.__class__.__dict__:
                o = object.__getattribute__(self, s)
                if isinstance(o, Field):
                    layout.append(s)

        for s in layout:
            o = object.__getattribute__(self, s)
            init.append(self.sanitize_init(o.value))

            if isinstance(o.type, str):
                type = o.type
                mytype = type
                field = s
            elif isinstance(o.type, Array):
                mytype = o.type.type
                type = mytype + '*'
                if o.type.size is None:
                    size = '[]'
                elif isinstance(o.type.size, int):
                    size = '[%d]' % o.type.size
                elif isinstance(o.type.size, list):
                    size = ''
                    for v in o.type.size:
                        size += '[%d]' % v
                field = "%s%s" % (s, size)

            content += "%s %s;\n" % (mytype, field)
            fields.append(field)

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

        push_scope(self.__class__.__name__)
        push_decl()
        ret = self.spec()
        if ret == 'no spec':
            self.impl()  # TODO: add pipeline state
            self.state = self.state.type(instance=False)
            scope, collection = pop_scope()
            decl = pop_decl()
            self.scope = decl + scope

        else:
            scope_spec, collection_spec = pop_scope()
            push_scope(self.__class__.__name__)
            self.impl()  # TODO: add pipeline state
            self.state = self.state.type(instance=False)
            scope_impl, collection_impl = pop_scope()
            decl = pop_decl()
            self.scope = decl + [program.Spec(scope_spec), program.Impl(scope_impl)]

    @abstractmethod
    def impl(self):
        pass

    def spec(self):
        return 'no spec'

