from graph import *
from thread_allocation import *


class StateInstance:
    def __init__(self, state, name):
        self.state = state
        self.name = name


class ElementInstance:
    def __init__(self, element, name, args=[]):
        self.element = element
        self.name = name
        self.args = args


class Connect:
    def __init__(self, ele1, ele2, out1=None, in2=None):
        self.ele1 = ele1
        self.ele2 = ele2
        self.out1 = out1
        self.in2 = in2


class Program:
    def __init__(self, *statments):
        self.statements = statments


class Composite:
    def __init__(self, name, inports, outports, state_params, program):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.state_params = state_params
        self.program = program


class CompositeInstance:
    def __init__(self, element, name, args=[]):
        self.element = element
        self.name = name
        self.args = args


class InternalThread:
    def __init__(self, name):
        self.element_instance = name


class ExternalAPI:
    def __init__(self, name):
        self.element_instance = name


class GraphGenerator:
    def __init__(self):
        self.graph = Graph()
        self.composites = {}
        self.composite_instances = {}
        self.env = {}

        self.threads_api = set()
        self.threads_internal = set()

    @staticmethod
    def get_node_name(stack, name):
        if len(stack) > 0:
            return "_" + "_".join(stack) + "_" + name
        else:
            return name

    def check_composite_port(self, composite_name, port_name, port_value):
        if not len(port_value) == 2:
            raise TypeError("The value of port '%s' of composite '%s' should be a pair of (internal instance, port)." %
                            (port_name, composite_name))

    def lookup(self, table, key):
        if key in table:
            return table[key]
        elif "__up__" in table:
            return self.lookup(table["__up__"], key)
        else:
            raise Exception("State instance '%s' is undefined." % key)

    def get_state_name(self, name):
        return self.lookup(self.env, name)[1]

    def get_state_type(self, name):
        return self.lookup(self.env, name)[0]

    def put_state(self, used_name, type, real_name):
        self.env[used_name] = (type, real_name)

    def push_scope(self, composite, state_params, state_args):
        params_types = [x[0] for x in state_params]
        args_types = [self.get_state_type(x) for x in state_args]
        used_names = [x[1] for x in state_params]
        real_names = [self.get_state_name(x) for x in state_args]

        env = dict()
        env["__up__"] = self.env
        self.env = env

        if not(len(state_params) == len(state_args)):
            raise Exception("Composite '%s' requires '%d' state parameters, but '%d' are given."
                            % (composite.name, len(state_params), len(state_args)))

        if not(params_types == args_types):
            raise Exception("Composite '%s' requires '%d' state parameters, but '%d' are given."
                            % (composite.name, params_types, args_types))

        for i in range(len(state_args)):
            self.put_state(used_names[i], args_types[i], real_names[i])

    def pop_scope(self):
        self.env = self.env["__up__"]

    def interpret(self, x, stack=[]):
        if isinstance(x, Program):
            for s in x.statements:
                self.interpret(s, stack)
        elif isinstance(x, Element):
            self.graph.addElement(x)
        elif isinstance(x, State):
            self.graph.addState(x)
        elif isinstance(x, ElementInstance):
            self.env[x.name] = "element"
            self.graph.newElementInstance(x.element, self.get_node_name(stack, x.name),
                                          [self.get_state_name(arg) for arg in x.args])
        elif isinstance(x, StateInstance):
            new_name = self.get_node_name(stack, x.name)
            self.put_state(x.name, x.state, new_name)
            self.graph.newStateInstance(x.state, new_name)
        elif isinstance(x, Connect):
            self.interpret_Connect(x, stack)
        elif isinstance(x, Composite):
            self.composites[x.name] = x
        elif isinstance(x, CompositeInstance):
            self.interpret_CompositeInstance(x, stack)
            self.env[x.name] = "composite"
        elif isinstance(x, InternalThread):
            self.threads_internal.add(self.get_node_name(stack, x.element_instance))
        elif isinstance(x, ExternalAPI):
            self.threads_api.add(self.get_node_name(stack, x.element_instance))
        else:
            raise Exception("GraphGenerator: unimplemented for %s." % x)

    def interpret_Connect(self, x, stack):
        (name1, out1) = self.adjust_name(x.ele1, x.out1, "output")
        (name2, in2) = self.adjust_name(x.ele2, x.in2, "input")
        self.graph.connect(self.get_node_name(stack, name1), self.get_node_name(stack, name2), out1, in2)

    def adjust_name(self, ele_name, port_name, type):
        if ele_name in self.composite_instances:
            if port_name:
                ports = []
                if type == "input":
                    ports += self.composite_instances[ele_name].inports
                else:
                    ports += self.composite_instances[ele_name].outports
                ports = [x for x in ports if x.name == port_name]
                if len(ports) == 0:
                    raise UndefinedPort("Port '%s' of instance '%s' is undefined." % (port_name, ele_name))
                return ele_name + "_" + port_name, None
            else:
                ports = []
                if type == "input":
                    ports += self.composite_instances[ele_name].inports
                else:
                    ports += self.composite_instances[ele_name].outports
                if len(ports) == 0:
                    raise Exception("Composite '%s' has no %s port, so it cannot be connected." % (ele_name, type))
                elif len(ports) > 1:
                    raise Exception("Composite '%s' has multiple %s ports. Need to specify which port to connect to."
                                    % (ele_name, type))
                else:
                    port_name = ports[0].name
                    return ele_name + "_" + port_name, None
        else:
            return ele_name, port_name

    def interpret_CompositeInstance(self, x, stack):
        new_stack = stack + [x.name]
        composite = self.composites[x.element]
        self.composite_instances[x.name] = composite
        self.push_scope(composite, composite.state_params, x.args)
        self.interpret(composite.program, new_stack)

        # Create element instances for input ports, and connect the interface elements to internal elements.
        for port in composite.inports:
            portname = port.name
            self.check_composite_port(composite.name, portname, port.argtypes)
            (internal_name, internal_port) = port.argtypes
            is_composite = self.lookup(self.env,  internal_name) == "composite"
            if is_composite:  # Composite
                internal_name = internal_name + "_" + internal_port
                internal_port = "in"
            internal_name = self.get_node_name(new_stack, internal_name)

            try:
                argtypes = self.graph.get_inport_argtypes(internal_name, internal_port) # TODO: better error message
                ele = self.graph.get_identity_element(argtypes)
                instance_name = self.get_node_name(stack, x.name + "_" + portname)
                self.graph.addElement(ele)
                self.graph.newElementInstance(ele.name, instance_name)
                self.graph.connect(instance_name, internal_name, None, internal_port)
            except UndefinedInstance:
                if is_composite:
                    raise UndefinedPort("Port '%s' of composite instance '%s' is undefined, but composite '%s' attempts to use it."
                                        % (port.argtypes[1], port.argtypes[0], composite.name))
                else:
                    raise UndefinedInstance("Element instance '%s' is undefined, but composite '%s' attempts to use it."
                                            % (port.argtypes[0], x.name))
            except UndefinedPort:
                raise UndefinedPort("Port '%s' of element instance '%s' is undefined, but composite '%s' attempts to use it."
                                    % (port.argtypes[1], port.argtypes[0], composite.name))


        # Create element instances for output ports, and connect the interface elements to internal elements.
        for port in composite.outports:
            portname = port.name
            self.check_composite_port(composite.name, portname, port.argtypes)
            (internal_name, internal_port) = port.argtypes
            is_composite = self.lookup(self.env,  internal_name) == "composite"
            if is_composite:  # Composite
                internal_name = internal_name + "_" + internal_port
                internal_port = "out"
            internal_name = self.get_node_name(new_stack, internal_name)

            try:
                argtypes = self.graph.get_outport_argtypes(internal_name, internal_port) # TODO: better error message
                ele = self.graph.get_identity_element(argtypes)
                instance_name = self.get_node_name(stack, x.name + "_" + portname)
                self.graph.addElement(ele)
                self.graph.newElementInstance(ele.name, instance_name)
                self.graph.connect(internal_name, instance_name, internal_port, None)
            except UndefinedInstance:
                if is_composite:
                    raise UndefinedPort("Port '%s' of composite instance '%s' is undefined, but composite '%s' attempts to use it."
                                        % (port.argtypes[1], port.argtypes[0], composite.name))
                else:
                    raise UndefinedInstance("Element instance '%s' is undefined, but composite '%s' attempts to use it."
                                            % (port.argtypes[0], x.name))
            except UndefinedPort:
                raise UndefinedPort("Port '%s' of element instance '%s' is undefined, but composite '%s' attempts to use it."
                                    % (port.argtypes[1], port.argtypes[0], composite.name))


        self.pop_scope()

    def allocate_resources(self):
        """
        Insert necessary elements for resource mapping and join elements. This method mutates self.graph
        """
        t = ThreadAllocator(self.graph, self.threads_api, self.threads_internal)
        t.transform()
