from abc import ABCMeta, abstractmethod
from collection import InstancesCollection
import graph
import program
import desugaring
import compiler

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


def scope_prepend(x):
    scope[-1].insert(0, x)


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

    def __str__(self):
        return "port:%s" % self.name

    def disable_collect(self):
        self.collecting = False

    def get_args(self):
        return self.element_ports[0].args


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


class API(Composite):
    def __init__(self, name, default_return=None, process=None):
        Composite.__init__(self, name)

        if len(self.inports) == 0:
            input = []
        elif len(self.inports) == 1:
            input = self.inports[0].get_args()
        else:
            order = self.args_order()
            assert set(order) == set(self.inports), \
                ("API.order %s is not the same as API's input ports %s" %
                 ([str(x) for x in order], [str(x) for x in self.inports]))
            input = []
            for p in order:
                input += p.get_args()

        if len(self.outports) == 0:
            output = None
        elif len(self.outports) == 1:
            args = self.outports[0].get_args()
            if len(args) == 0:
                output = None
            elif len(args) == 1:
                output = args[0]
            else:
                raise Exception("Output port '%s' of API '%s' returns more than one value." %
                                (self.outports[0].name, self.name))
        else:
            raise Exception("API '%s' has more than one output port: %s." % (self.name, self.outports))

        t = APIThread(name, [x for x in input], output, default_val=default_return)
        t.run(self)

    @abstractmethod
    def implementation(self):
        pass

    def args_order(self):
        raise Exception("This function needs to be overloaded.")


class InternalLoop(Composite):
    def __init__(self, name, process=None):
        Composite.__init__(self, name)

        t = InternalThread(name)
        t.run(self)

    @abstractmethod
    def implementation(self):
        pass


####################### Thread ######################


class Thread:
    def __init__(self, name):
        self.name = name

    def run(self, *instances):
        for i in range(len(instances)):
            instance = instances[i]
            if isinstance(instance, Element):
                scope[-1].append(program.ResourceMap(self.name, instance.name))
            elif isinstance(instance, Composite):
                if instance.collection.impl:
                    scope_append(program.Spec([program.ResourceMap(self.name, x) for x in instance.collection.spec]))
                    scope_append(program.Impl([program.ResourceMap(self.name, x) for x in instance.collection.impl]))
                else:
                    for name in instance.collection.spec:
                        scope_append(program.ResourceMap(self.name, name))
            # elif isinstance(instance, SpecImplInstance):
            #     scope[-1].append(Spec([ResourceMap(self.name, x) for x in instance.spec_instances_names]))
            #     scope[-1].append(Impl([ResourceMap(self.name, x) for x in instance.impl_instances_names]))
            else:
                raise Exception("Thread.run unimplemented for '%s'" % instance)

    def run_order(self, *instances):
        self.run(*instances)
        run_order(*instances)


def run_order(*instances):
    for i in range(len(instances) - 1):
        if isinstance(instances[i], list):
            scope_append(program.ResourceOrder([x.name for x in instances[i]], instances[i + 1].name))
        else:
            scope_append(program.ResourceOrder(instances[i].name, instances[i + 1].name))


class APIThread(Thread):
    def __init__(self, name, call_types, return_types, default_val=None):
        api = program.APIFunction(name, call_types, return_types, default_val)
        scope_prepend(api)
        Thread.__init__(self, name)


class InternalThread(Thread):
    def __init__(self, name):
        name = get_node_name(name)
        trigger = program.InternalTrigger(name)
        scope_prepend(trigger)
        Thread.__init__(self, name)

####################### Compiler #########################
class Compiler:
    def __init__(self):
        self.desugar_mode = "impl"
        self.resource = True
        self.remove_unused = True

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

        # Compiler option
        self.I = None

    def generate_graph(self, filename="tmp"):
        assert len(scope) == 1, "Compile error: there are multiple scopes remained."
        p1 = program.Program(*scope[0])
        p2 = desugaring.desugar(p1, self.desugar_mode)
        dp = desugaring.insert_fork(p2)
        g = compiler.generate_graph(dp, self.resource, self.remove_unused, filename, None)  # TODO: state_mapping
        return g

    def generate_code(self):
        compiler.generate_code(self.generate_graph(), ".c", self.testing, self.include)

    def generate_code_and_run(self, expect=None):
        compiler.generate_code_and_run(self.generate_graph(), self.testing, self.desugar_mode, expect, self.include, self.depend)

    def generate_code_and_compile(self):
        compiler.generate_code_and_compile(self.generate_graph(), self.testing, self.desugar_mode, self.include, self.depend)

    def generate_code_as_header(self, header='tmp'):
        compiler.generate_code_as_header(self.generate_graph(header), self.testing, self.desugar_mode, self.include)

    def compile_and_run(self, name):
        compiler.compile_and_run(name, self.depend)


