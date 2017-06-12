from abc import ABCMeta, abstractmethod
from collection import InstancesCollection
import graph
import program

######################## Scope ##########################
scope = [[]]
stack = []
inst_collection = [InstancesCollection()]


def reset():
    global scope, stack, inst_collection
    scope = [[]]
    stack = []
    inst_collection = [InstancesCollection()]


def get_scope():
    return scope


def scope_append(x):
    scope[-1].append(x)
    if isinstance(x, program.ElementInstance):
        inst_collection[-1].add(x.name)
    elif isinstance(x, program.Connect):
        inst_collection[-1].add(x.ele1)
        inst_collection[-1].add(x.ele2)


def push_scope(name):
    scope.append([])
    stack.append(name)
    inst_collection.append(InstancesCollection())


def pop_scope():
    global scope, stack, inst_collection
    stack = stack[:-1]
    my_scope = scope[-1]
    scope = scope[:-1]
    scope[-1] = scope[-1] + my_scope
    my_collection = inst_collection[-1]
    inst_collection = inst_collection[:-1]
    return my_collection


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name

####################### Data type ########################

Int = 'int'
Size = 'size_t'


def Uint(bits):
    return 'uint%d_t' % bits

###################### Port #######################

class Port(object):
    def __init__(self, *args):
        self.name = None
        self.element = None
        self.args = args

    def __str__(self):
        return "port '%s' of element '%s'" % (self.name, self.element)


class Input(Port):
    pass


class Output(Port):
    def __rshift__(self, other):
        if isinstance(other, Connectable):
            other.rshift__reversed(self)
        elif isinstance(other, CompositePort):
            other.rshift__reversed(self)
        elif isinstance(other, Input):
            assert self.args == other.args, "Illegal to connect %s of type %s to %s of type %s." \
                                            % (self, self.args, other, other.args)
            c = program.Connect(self.element, other.element, self.name, other.name)
            scope_append(c)
        else:
            raise Exception("Attempt to connect element '%s' to %s, which is not an element, a composite, or an input port." %
                            (self.element, other))

        return other


class CompositePort(object):
    def __init__(self, port):
        self.name = port.name
        self.composite = port.element
        self.element_ports = []
        self.collecting = True

    def disable_collect(self):
        self.collecting = False


class CompositeInput(CompositePort):
    def __rshift__(self, other):
        if isinstance(other, Connectable):
            other.rshift__reversed(self)
        elif isinstance(other, Input):
            assert self.collecting, \
                ("Illegal to connect input port '%s' of composite '%s' to %s, which is an input port, outside the composite implementation." %
                 (self.name, self.composite, other))
            self.element_ports.append(other)
        elif isinstance(other, CompositeInput):
            for p in other.element_ports:
                self >> p
        else:
            raise Exception("Attempt to connect input port '%s' of composite '%s' to %s, which is not an element, a composite, or an input port." %
                            (self.name, self.composite, other))
        return other

    def rshift__reversed(self, other):
        for port in self.element_ports:
            other >> port
        return self


class CompositeOutput(CompositePort):
    def __rshift__(self, other):
        if isinstance(other, Connectable):
            other.rshift__reversed(self)
        else:
            for port in self.element_ports:
                port >> other
        return other

    def rshift__reversed(self, other):
        if isinstance(other, Output):
            assert self.collecting, \
                ("Illegal to connect %s, which is an output port, to output port '%s' of composite '%s' outside the composite implementation." %
                (other, self.name, self.composite))
            self.element_ports.append(other)
        else:
            raise Exception("Attempt to connect %s, which is not an output of an element, to output port '%s' of composite '%s'." %
                            (other, self.name, self.composite))
        return self

###################### Element, Composite #######################

class Connectable(object):

    def __init__(self, name=None, params=[]):
        self.id = 0
        if name is None:
            name = self.__class__.__name__ + str(self.id)
            self.id += 1
        name = get_node_name(name)
        self.name = name

        self.init(*params)
        self.port()

        self.inports = []
        self.outports = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Port):
                o.name = s
                o.element = name
                if isinstance(o, Input) or isinstance(o, CompositeInput):
                    self.inports.append(o)
                else:
                    self.outports.append(o)

    def init(self, *params):
        pass

    @abstractmethod
    def port(self):
        pass

    def __rshift__(self, other):
        assert len(self.outports) == 1, \
            "Attempt to connect '%s', which has zero or multiple output ports, to '%s'." % (self.name, other)
        self.outports[0] >> other
        return other

    def rshift__reversed(self, other):
        assert len(self.inports) == 1, \
            "Attempt to connect '%s' to '%s', which has zero or multiple input ports." % (self.name, other)
        other >> self.inports[0]
        return self


class Element(Connectable):
    defined = set()

    def __init__(self, name=None, params=[]):
        Connectable.__init__(self, name, params)
        self.code = ''
        self.run()

        unique = self.__class__.__name__ + "_".join([str(p) for p in params])
        if unique not in Element.defined:
            Element.defined.add(unique)
            inports = [graph.Port(p.name, p.args) for p in self.inports]
            outports = [graph.Port(p.name, p.args) for p in self.outports]
            e = graph.Element(unique, inports, outports, self.code)
            scope_append(e)

        inst = program.ElementInstance(unique, self.name)
        scope_append(inst)

    @abstractmethod
    def run(self):
        pass

    def run_c(self, code):
        self.code = code

    def run_c_element(self, name):
        raise Exception("Unimplemented")

    def run_c_function(self, name):
        raise Exception("Unimplemented")

    # def __getattribute__(self, item):
    #     x = object.__getattribute__(self, item)
    #     if isinstance(x, Port):
    #         x.element = self
    #     return x


class Composite(Connectable):

    def __init__(self, name=None, params=[]):
        Connectable.__init__(self, name, params)
        self.inports = [CompositeInput(p) for p in self.inports]
        self.outports = [CompositeOutput(p) for p in self.outports]

        for p in self.inports + self.outports:
            self.__dict__[p.name] = p

        push_scope(self.name)
        self.implementation()
        self.collection = pop_scope()

        for p in self.inports + self.outports:
            p.disable_collect()

    @abstractmethod
    def implementation(self):
        pass



#######################



