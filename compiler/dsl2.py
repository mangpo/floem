from state import *
from workspace import *
import re
import copy

def reset():
    Element.defined = set()
    State.defined = set()
    State.id = 0
    Connectable.id = 0
    workspace_reset()

###################### Port #######################

class Port(object):
    def __init__(self, *args):
        self.name = None
        self.element = None
        self.args = [string_type(x) for x in args]

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
        elif isinstance(other, SpecImplPort):
            other.rshift__reversed(self)
        elif isinstance(other, Input):
            if not self.args == other.args:
                if len(other.args) > 0 or len(other.element.inports) > 1:
                    raise Exception("Illegal to connect %s of type %s to %s of type %s." %
                                    (self, self.args, other, other.args))
            c = program.Connect(self.element.name, other.element.name, self.name, other.name)
            scope_append(c)
        else:
            raise Exception("Attempt to connect element '%s' to %s, which is not an element, a composite, or an input port." %
                            (self.element, other))

        return other


class CompositePort(object):
    def __init__(self, port=None, composite=None):
        if port:
            self.name = port.name
        else:
            self.name = None
        self.composite = composite
        self.element_ports = []
        self.collecting = True

    def __str__(self):
        return "port:%s" % self.name

    def disable_collect(self):
        self.collecting = False

    def get_args(self):
        return self.element_ports[0].args


class CompositeInput(CompositePort):
    def clone(self):
        x = CompositeInput()
        x.name = self.name
        x.composite = self.composite
        x.element_ports = copy.copy(self.element_ports)
        x.collecting = True
        return x

    def __rshift__(self, other):
        if isinstance(other, Input):
            assert self.collecting, \
                ("Illegal to connect input port '%s' of composite '%s' to %s, which is an input port, outside the composite implementation." %
                 (self.name, self.composite, other))
            self.element_ports.append(other)
        elif isinstance(other, CompositeInput):
            for p in other.element_ports:
                self >> p
        elif isinstance(other, Connectable):
            other.rshift__reversed(self)
        else:
            raise Exception("Attempt to connect input port '%s' of composite '%s' to %s, which is not an element, a composite, or an input port." %
                            (self.name, self.composite, other))
        return other

    def rshift__reversed(self, other):
        for port in self.element_ports:
            other >> port
        return self


class CompositeOutput(CompositePort):
    def clone(self):
        x = CompositeOutput()
        x.name = self.name
        x.composite = self.composite
        x.element_ports = copy.copy(self.element_ports)
        x.collecting = True
        return x

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


def insert_spec_impl_scope(scope_spec, scope_impl, collection_spec, collection_impl):
    scope_append(program.Spec(scope_spec))
    scope_append(program.Impl(scope_impl))
    collection_spec.impl = collection_impl.spec
    get_current_collection().union(collection_spec)


class SpecImplPort(object):

    def __init__(self, spec, impl):
        if isinstance(spec, Input) or isinstance(spec, SpecImplInput):
            self.spec = CompositeInput(spec, impl)
            self.impl = None
            self.name = self.spec.name
        elif isinstance(spec, Output) or isinstance(spec, SpecImplOutput):
            self.spec = CompositeOutput(spec, impl)
            self.impl = None
            self.name = self.spec.name
        else:
            self.name = spec.name
            self.spec = spec
            self.impl = impl

    def __rshift__(self, other):
        if self.impl:
            push_scope(self.name)
            self.spec >> other
            scope_spec, collection_spec = pop_scope()
            push_scope(self.name)
            self.impl >> other
            scope, collection = pop_scope()

            insert_spec_impl_scope(scope_spec, scope, collection_spec, collection)
        else:
            self.spec >> other
        return other

    def rshift__reversed(self, other):
        if self.impl:
            push_scope(self.name)
            other >> self.spec
            scope_spec, collection_spec = pop_scope()
            push_scope(self.name)
            other >> self.impl
            scope, collection = pop_scope()

            insert_spec_impl_scope(scope_spec, scope, collection_spec, collection)
        else:
            other >> self.spec
        return self

    def disable_collect(self):
        self.spec.disable_collect()
        if self.impl:
            self.impl.disable_collect()

    def get_args(self):
        return self.spec.get_args()

class SpecImplInput(SpecImplPort):
    # for collecting
    def __rshift__(self, other):
        if isinstance(other, SpecImplInput):
            self.spec >> other.spec
            if other.impl:
                if self.impl:
                    self.impl >> other.impl
                else:
                    self.impl = other.impl.clone()
        elif isinstance(other, Input):
            self.spec >> other
        elif isinstance(other, Connectable):
            other.rshift__reversed(self)
        else:
            SpecImplPort.__rshift__(self, other)
        return other


class SpecImplOutput(SpecImplPort):
    # for collecting
    def __rshift__(self, other):
        if isinstance(other, SpecImplOutput):
            self.spec >> other.spec
            if self.impl:
                if other.impl:
                    self.impl >> other.impl
                else:
                    other.impl = self.impl.clone()
        elif isinstance(other, Output):
            self.sepc >> other
        elif isinstance(other, Connectable):
            other.rshift__reversed(self)
        else:
            SpecImplPort.__rshift__(self, other)
        return other


###################### Element, Composite #######################

class Connectable(object):
    id = 0

    def __str__(self):
        return self.name

    def __init__(self, name=None, states=[], configure=[]):
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
                o.element = self
                if isinstance(o, Input) or isinstance(o, CompositeInput):
                    self.inports.append(o)
                else:
                    self.outports.append(o)
            elif isinstance(o, list) and len(o) > 0 and isinstance(o[0], Port):
                for i in range(len(o)):
                    p = o[i]
                    p.name = s + str(i)
                    p.element = self
                    if isinstance(p, Input) or isinstance(p, CompositeInput):
                        self.inports.append(p)
                    else:
                        self.outports.append(p)

    def configure(self, *params):
        pass

    def states(self, *params):
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
    class_defined = set()
    class_id = 0
    all_defined = set()
    defined = False

    def __init__(self, name=None, states=[], configure=[], create=True):
        self.special = None
        self.def_fields = None
        self.used_fields = None
        self.code = ''

        if not self.__class__.defined:  # subclass has not declared before
            self.__class__.defined = True
            if self.__class__.__name__ in Element.class_defined:
                self.__class__.__name__ += str(Element.class_id)
                Element.class_id += 1
            Element.class_defined.add(self.__class__.__name__)

        # this comes after self.__class__.__name__ but before collection_states
        Connectable.__init__(self, name, states, configure)
        self.impl()
        states_decls, states = self.collect_states()

        if len(configure) == 0:
            unique = self.__class__.__name__
        else:
            unique = self.__class__.__name__ + "_" + "_".join([str(p) for p in configure])
        if unique not in Element.all_defined:
            Element.all_defined.add(unique)
            inports = [graph.Port(p.name, p.args) for p in self.inports]
            outports = [graph.Port(p.name, p.args) for p in self.outports]
            e = graph.Element(unique, inports, outports, self.code, states_decls)
            e.special = self.special
            decl_append(e)

        inst = program.ElementInstance(unique, self.name, states)
        self.instance = inst
        if create:
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
            if isinstance(o, Persistent):
                assert isinstance(value, o.type), "%s.%s should be assign to a value of type %s." \
                                                  % (self.name, key, o.type.__name__)
                super(Connectable, self).__setattr__(key, Persistent(o.type, value))
                return
            elif isinstance(o, PerPacket):
                raise Exception("Per-packet state %s.%s should not be initialized with a persistent state."
                                % (self.name, key))
        super(Connectable, self).__setattr__(key, value)

    def collect_states(self):
        defs = []
        states = []
        for s in self.__dict__:
            o = self.__dict__[s]
            if isinstance(o, Persistent):
                if not o.value:
                    raise Exception("State %s.%s must be initialized." % (self.name, s))
                defs.append((o.type.__name__, s))
                states.append(o.value.name)
        return defs, states

    def defs(self, *fields):
        self.def_fields = fields

    def uses(self, *fields):
        self.used_fields = fields


class ElementOneInOut(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output()

    @abstractmethod
    def impl(self):
        pass


class Composite(Connectable):

    def assign_ports(self, l):
        for p in l:
            if p.name in self.__dict__:
                self.__dict__[p.name] = p
            else:
                for name in self.__dict__:
                    o = self.__dict__[name]
                    m = re.match(name, p.name)
                    if m and isinstance(o, list):
                        index = int(p.name[len(name):])
                        if index < len(o) and isinstance(o[index], Port) or isinstance(o[index], SpecImplPort):
                            o[index] = p
                            break

    def __init__(self, name=None, states=[], configure=[]):
        Connectable.__init__(self, name, states, configure)
        self.inports = [SpecImplInput(p, self.name) for p in self.inports]
        self.outports = [SpecImplOutput(p, self.name) for p in self.outports]
        self.assign_ports(self.inports + self.outports)

        push_scope(self.__class__.__name__)
        ret = self.spec()
        if ret == 'no spec':
            self.spec_impl = False
            #push_scope(self.name)
            self.impl()
            self.collection = merge_scope()
            self.collection_spec = None
        else:
            self.spec_impl = True
            scope_spec, collection_spec = pop_scope()
            inports_spec = self.inports
            outports_spec = self.outports

            self.inports = [SpecImplInput(p, self.name) for p in self.inports]
            self.outports = [SpecImplOutput(p, self.name) for p in self.outports]
            self.assign_ports(self.inports + self.outports)

            push_scope(self.__class__.__name__)
            self.impl()
            scope, collection = pop_scope()
            inports = self.inports
            outports = self.outports

            self.collection = collection_spec
            insert_spec_impl_scope(scope_spec, scope, self.collection, collection)

            self.inports = []
            self.outports = []
            for i in range(len(inports)):
                spec = inports_spec[i]
                impl = inports[i]
                spec.impl = impl.spec
                self.inports.append(spec)
            for i in range(len(outports)):
                spec = outports_spec[i]
                impl = outports[i]
                spec.impl = impl.spec
                self.outports.append(spec)

            self.assign_ports(self.inports + self.outports)


        for p in self.inports + self.outports:
            p.disable_collect()

    @abstractmethod
    def impl(self):
        pass

    def spec(self):
        return 'no spec'


class API(Composite):
    def __init__(self, name, default_return=None, process=None):
        self.process = process
        self.default_return = default_return
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
        self.check_api_start_node()

        t = APIThread(name, [x for x in input], output, default_val=self.default_return)
        t.run(self)

        if self.process:
            scope_append(program.ProcessMap(self.process, name))

    @abstractmethod
    def impl(self):
        pass

    def args_order(self):
        raise Exception("This function needs to be overloaded.")

    def check_api_start_node(self):
        spec_inports = [p.spec for p in self.inports]
        if not self.spec_impl:
            insert = self.need_insert(spec_inports)
            if insert:
                push_scope(self.name)
                self.create_api_start_node(spec_inports)
                addition = merge_scope()
                self.collection.union_spec(addition)
        else:
            insert = self.need_insert(spec_inports)
            if insert:
                push_scope(self.name)
                self.create_api_start_node(spec_inports)
                scope, addition = pop_scope()
                scope_append(program.Spec(scope))
                self.collection.union_spec(addition)

            impl_inports = [p.impl for p in self.inports]
            insert = self.need_insert(impl_inports)
            if insert:
                push_scope(self.name)
                self.create_api_start_node(impl_inports)
                scope, addition = pop_scope()
                scope_append(program.Impl(scope))
                self.collection.union_impl(addition)

    @staticmethod
    def need_insert(inports):
        elements = set()
        for x in inports:
            for port in x.element_ports:
                elements.add(port.element)
        count = len(elements)
        return count > 1

    def create_api_start_node(self, inports):
        src_in = ""
        src_out = ""
        for i in range(len(inports)):
            types = inports[i].element_ports[0].args
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

        # inports = self.inports

        class APIStart(Element):
            def configure(self, parent_name):
                self.inp = [Input(*x.element_ports[0].args) for x in inports]
                self.out = [Output(*x.element_ports[0].args) for x in inports]

            def impl(self):
                self.run_c(src)

        start = APIStart(name=start_name, configure=[self.name])
        for i in range(len(inports)):
            for port in inports[i].element_ports:
                start.out[i] >> port

            inports[i].element_ports = [start.inp[i]]


class InternalLoop(Composite):
    def __init__(self, name, process=None):
        self.process = process
        Composite.__init__(self, name)

        t = InternalThread(name)
        t.run(self)

        if self.process:
            scope_append(program.ProcessMap(self.process, name))

    @abstractmethod
    def impl(self):
        pass

####################### Inject & Probe ######################
def create_inject(name, type, size, func, interval=50):
    prefix = name + '_'

    class Data(State):
        data = Field(Array(type, size))
        p = Field(Int)

        def init(self):
            self.p = 0
    Data.__name__ = prefix + Data.__name__
    data = Data()

    class Inject(Element):
        this = Persistent(Data)

        def configure(self):
            self.out = Output(type)
            self.this = data

        def impl(self):
            src = r'''
                    if(this->p >= %d) { printf("Error: inject more than available entries.\n"); exit(-1); }
                    int temp = this->p;
                    this->p++;''' % size
            src += "output { out(this->data[temp]); }"
            self.run_c(src)

    Inject.__name__ = prefix + Inject.__name__
    scope_prepend(program.PopulateState(name, data.name, Data.__name__, type, size, func, interval))
    return Inject


def create_probe(name, type, size, func):
    prefix = name + '_'

    class Data(State):
        data = Field(Array(type, size))
        p = Field(Int)

        def init(self):
            self.p = 0

    Data.__name__ = prefix + Data.__name__
    data = Data()

    class Probe(Element):
        this = Persistent(Data)

        def configure(self):
            self.inp = Input(type)
            self.out = Output(type)
            self.this = data

        def impl(self):
            append = r'''
                    if(this->p >= %d) { printf("Error: probe more than available entries.\n"); exit(-1); }
                    this->data[this->p] = x;
                    this->p++;''' % size
            src = "(%s x) = inp(); %s output { out(x); }" % (type, append)
            self.run_c(src)

    Probe.__name__ = prefix + Probe.__name__
    scope_prepend(program.CompareState(name, data.name, Data.__name__, type, size, func))
    return Probe


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
        trigger = program.InternalTrigger(name)
        scope_prepend(trigger)
        Thread.__init__(self, name)


def master_process(p):
    scope_append(program.MasterProcess(p))
