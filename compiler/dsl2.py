from abc import ABCMeta, abstractmethod

import graph
import program
from state import *
from workspace import scope_append, scope_prepend, push_scope, pop_scope, get_node_name, Compiler

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
    id = 0

    def __init__(self, name=None, states=[], configure=[]):
        self.id = 0
        if name is None:
            name = self.__class__.__name__ + str(self.__class__.id)
            self.__class__.id += 1
        name = get_node_name(name)
        self.name = name

        self.configure(*configure)
        self.states(*states)

        self.inports = []
        self.outports = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if s in ['inports', 'outports']:
                continue
            if isinstance(o, Port):
                o.name = s
                o.element = name
                if isinstance(o, Input) or isinstance(o, CompositeInput):
                    self.inports.append(o)
                else:
                    self.outports.append(o)
            elif isinstance(o, list) and len(o) > 0 and isinstance(o[0], Port):
                for i in range(len(o)):
                    p = o[i]
                    p.name = s + str(i)
                    p.element = name
                    if isinstance(p, Input) or isinstance(p, CompositeInput):
                        self.inports.append(p)
                    else:
                        self.outports.append(p)

    def configure(self, *params):
        pass

    def states(self, *params):
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

    def __init__(self, name=None, states=[], configure=[]):
        Connectable.__init__(self, name, states, configure)
        self.code = ''
        self.impl()
        defs, states = self.collect_states()

        if len(configure) == 0:
            unique = self.__class__.__name__
        else:
            unique = self.__class__.__name__ + "_" + "_".join([str(p) for p in configure])
        if unique not in Element.defined:
            Element.defined.add(unique)
            inports = [graph.Port(p.name, p.args) for p in self.inports]
            outports = [graph.Port(p.name, p.args) for p in self.outports]
            e = graph.Element(unique, inports, outports, self.code, defs)
            scope_append(e)

        inst = program.ElementInstance(unique, self.name, states)
        scope_append(inst)

    @abstractmethod
    def impl(self):
        pass

    def run_c(self, code):
        self.code = code

    def run_c_element(self, name):
        raise Exception("Unimplemented")

    def run_c_function(self, name):
        raise Exception("Unimplemented")

    def __setattr__(self, key, value):
        if key in self.__class__.__dict__:
            o = self.__getattribute__(key)
            if isinstance(o, Field):
                assert isinstance(value, o.type), "%s.%s should be assign to a value of type %s." \
                                                  % (self.name, key, o.type.__name__)
                super(Connectable, self).__setattr__(key, Field(o.type, value))
                return
        super(Connectable, self).__setattr__(key, value)

    def collect_states(self):
        defs = []
        states = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Field):
                if o.value == 0:
                    raise Exception("State %s.%s must be initialized." % (self.name, s))
                defs.append((o.type.__name__, s))
                states.append(o.value.name)
        return defs, states


class Composite(Connectable):

    def __init__(self, name=None, states=[], configure=[]):
        Connectable.__init__(self, name, states, configure)
        self.inports = [CompositeInput(p) for p in self.inports]
        self.outports = [CompositeOutput(p) for p in self.outports]

        for p in self.inports + self.outports:
            self.__dict__[p.name] = p

        push_scope(self.name)
        self.impl()
        self.collection = pop_scope()

        for p in self.inports + self.outports:
            p.disable_collect()

    @abstractmethod
    def impl(self):
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

        # Insert an element for an API with multiple starting elements.
        elements = set()
        for x in self.inports:
            for port in x.element_ports:
                elements.add(port.element)
        count = len(elements)
        if count > 1:
            push_scope(self.name)
            self.create_api_start_node()
            addition = pop_scope()
            self.collection.union(addition)

        t = APIThread(name, [x for x in input], output, default_val=default_return)
        t.run(self)

    @abstractmethod
    def impl(self):
        pass

    def args_order(self):
        raise Exception("This function needs to be overloaded.")

    def create_api_start_node(self):
        src_in = ""
        src_out = ""
        for i in range(len(self.inports)):
            types = self.inports[i].element_ports[0].args
            types_args = []
            args = []
            for j in range(len(types)):
                arg = "x%d_%d" % (i, j)
                types_args.append("%s %s" % (types[j], arg))
                args.append(arg)
            types_args = ','.join(types_args)
            args = ','.join(args)
            src_in += "(%s) = inp%d();\n" % (types_args, i)
            src_out += "out%d(%s);\n" % (i, args)

        src = src_in
        src += "output {\n"
        src += src_out
        src += "}\n"

        start_name = "start"

        inports = self.inports

        class APIStart(Element):
            def configure(self, parent_name):
                self.inp = [Input(*x.element_ports[0].args) for x in inports]
                self.out = [Output(*x.element_ports[0].args) for x in inports]

            def impl(self):
                self.run_c(src)

        start = APIStart(name=start_name, configure=[self.name])
        for i in range(len(self.inports)):
            for port in self.inports[i].element_ports:
                start.out[i] >> port

            self.inports[i].element_ports = [start.inp[i]]


class InternalLoop(Composite):
    def __init__(self, name, process=None):
        Composite.__init__(self, name)

        t = InternalThread(name)
        t.run(self)

    @abstractmethod
    def impl(self):
        pass


####################### Thread ######################


class Thread:
    def __init__(self, name):
        self.name = name

    def run(self, *instances):
        for i in range(len(instances)):
            instance = instances[i]
            if isinstance(instance, Element):
                scope_append(program.ResourceMap(self.name, instance.name))
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

