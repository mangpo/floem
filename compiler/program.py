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
    def __init__(self, name, inports, outports, thread_ports, state_params, program):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.thread_ports = thread_ports
        self.state_params = state_params
        self.program = program


class CompositeInstance:
    def __init__(self, element, name, args=[]):
        self.element = element
        self.name = name
        self.args = args


class InternalTrigger:
    def __init__(self, name):
        self.element_instance = name


class ExternalTrigger:
    def __init__(self, name):
        self.element_instance = name


def get_node_name(stack, name):
    if len(stack) > 0:
        return "_" + "_".join(stack) + "_" + name
    else:
        return name


class APIFunction:
    def __init__(self, name, call_instance, call_port, return_instance, return_port, state_name=None):
        if (return_port) and (state_name is None):
            raise Exception("API function '%s' needs a return state when it has return ports." % name)
        self.name = name
        self.call_instance = call_instance
        self.call_port = call_port
        self.return_instance = return_instance
        self.return_port = return_port
        self.state_name = state_name


class GraphGenerator:
    def __init__(self):
        self.graph = Graph()
        self.composites = {}
        self.elements = {}
        self.env = {}

        self.threads_api = set()
        self.threads_internal = set()
        self.APIs = []

    def check_composite_port(self, composite_name, port_name, port_value):
        if not len(port_value) == 2:
            raise TypeError("The value of port '%s' of composite '%s' should be a pair of (internal instance, port)." %
                            (port_name, composite_name))

    def lookup(self, key):
        return self.lookup_recursive(self.env, key)

    def lookup_recursive(self, table, key):
        if key in table:
            return table[key]
        elif "__up__" in table:
            return self.lookup(key)
        else:
            raise Exception("'%s' is undefined." % str(key))

    def get_state_name(self, name):
        return self.lookup(name)[1]

    def get_state_type(self, name):
        return self.lookup(name)[0]

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

    def current_scope(self, name, construct):
        if name not in self.env:
            raise Exception("Instance '%s' must be defined in the same local scope as '%s' command."
                            % (name, construct))

    def interpret(self, x, stack=[]):
        if isinstance(x, Program):
            for s in x.statements:
                self.interpret(s, stack)
        elif isinstance(x, Element):
            self.elements[x.name] = x
            self.graph.addElement(x)
        elif isinstance(x, State):
            self.graph.addState(x)
        elif isinstance(x, ElementInstance):
            try:
                self.env[x.name] = self.elements[x.element]
            except KeyError:
                raise Exception("Element '%s' is undefined." % x.element)
            self.graph.newElementInstance(x.element, get_node_name(stack, x.name),
                                          [self.get_state_name(arg) for arg in x.args])
        elif isinstance(x, StateInstance):
            new_name = get_node_name(stack, x.name)
            self.put_state(x.name, x.state, new_name)
            self.graph.newStateInstance(x.state, new_name)
        elif isinstance(x, Connect):
            self.interpret_Connect(x, stack)
        elif isinstance(x, Composite):
            self.composites[x.name] = x
        elif isinstance(x, CompositeInstance):
            try:
                self.env[x.name] = self.composites[x.element]
            except KeyError:
                raise Exception("Composite '%s' is undefined." % x.element)
            self.interpret_CompositeInstance(x, stack)
        elif isinstance(x, InternalTrigger):
            self.current_scope(x.element_instance, "InternalTrigger")
            self.threads_internal.add(get_node_name(stack, x.element_instance))
        elif isinstance(x, ExternalTrigger):
            self.current_scope(x.element_instance, "ExternalTrigger")
            self.threads_api.add(get_node_name(stack, x.element_instance))
        elif isinstance(x, APIFunction):
            call_instance, call_port = self.convert_to_element_ports(x.call_instance, x.call_port, stack)
            return_instance, return_port = self.convert_to_element_ports(x.return_instance, x.return_port, stack)
            self.threads_api.add(call_instance)
            self.APIs.append(APIFunction(x.name, call_instance, call_port, return_instance, return_port, x.state_name))
        else:
            raise Exception("GraphGenerator: unimplemented for %s." % x)

    def interpret_Connect(self, x, stack):
        self.current_scope(x.ele1, "Connect")
        self.current_scope(x.ele2, "Connect")
        (name1, out1) = self.adjust_connection(x.ele1, x.out1, "output")
        (name2, in2) = self.adjust_connection(x.ele2, x.in2, "input")
        self.graph.connect(get_node_name(stack, name1), get_node_name(stack, name2), out1, in2)

    def convert_to_element_ports(self, call_instance, call_ports, stack):
        """
        Convert to (element, ports)
        :param call_instance: element or composite instance
        :param call_ports: element or composite ports
        :param stack: program scope
        :return: (element, ports)
        """
        self.current_scope(call_instance, "APIFunction")
        t = self.lookup(call_instance)
        if isinstance(t, Element):
            call_instance = get_node_name(stack, call_instance)
            return call_instance, call_ports
        elif isinstance(t, Composite):
            call_instance, call_ports = self.lookup((call_instance, call_ports))
            return call_instance, call_ports

    def adjust_connection(self, ele_name, port_name, type):
        t = self.lookup(ele_name)
        if isinstance(t, Composite):
            if port_name:
                ports = []
                if type == "input":
                    ports += t.inports  # TODO
                else:
                    ports += t.outports
                ports = [x for x in ports if x.name == port_name]
                if len(ports) == 0:
                    raise UndefinedPort("Port '%s' of instance '%s' is undefined." % (port_name, ele_name))
                return ele_name + "_" + port_name, None
            else:
                ports = []
                if type == "input":
                    ports += t.inports
                else:
                    ports += t.outports
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
        self.push_scope(composite, composite.state_params, x.args)
        self.interpret(composite.program, new_stack)

        # Check if ports connect to element in the current scope.
        for port in composite.inports + composite.outports + composite.thread_ports:
            self.current_scope(port.argtypes[0], "composite port")

        # Create element instances for input ports, and connect the interface elements to internal elements.
        for port in composite.inports:
            portname = port.name
            self.check_composite_port(composite.name, portname, port.argtypes)
            (internal_name, internal_port) = port.argtypes
            is_composite = isinstance(self.lookup(internal_name), Composite)
            if is_composite:  # Composite
                internal_name = internal_name + "_" + internal_port
                internal_port = "in"
            internal_name = get_node_name(new_stack, internal_name)

            try:
                argtypes = self.graph.get_inport_argtypes(internal_name, internal_port) # TODO: better error message
                ele = self.graph.get_identity_element(argtypes)
                instance_name = get_node_name(stack, x.name + "_" + portname)
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
            is_composite = isinstance(self.lookup(internal_name), Composite)
            if is_composite:  # Composite
                internal_name = internal_name + "_" + internal_port
                internal_port = "out"
            internal_name = get_node_name(new_stack, internal_name)

            try:
                argtypes = self.graph.get_outport_argtypes(internal_name, internal_port) # TODO: better error message
                ele = self.graph.get_identity_element(argtypes)
                instance_name = get_node_name(stack, x.name + "_" + portname)
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

        # Save port mapping into environment.
        threadport2element = dict()
        for port in composite.thread_ports + composite.inports + composite.outports:
            key = (x.name, port.name)
            pointer = port.argtypes
            if not isinstance(pointer, tuple) or not len(pointer) == 2:
                raise Exception("Port '%s' of composite '%s' should assign to a tuple of (name, port)."
                                % (port.name, composite.name))
            t = self.lookup(pointer[0])
            if isinstance(t, Element):
                if port in composite.thread_ports:
                    threadport2element[key] = (get_node_name(new_stack, pointer[0]), pointer[1])
                elif port in composite.inports:
                    threadport2element[key] = (get_node_name(stack, x.name + "_" + port.name), "in")
                elif port in composite.outports:
                    threadport2element[key] = (get_node_name(stack, x.name + "_" + port.name), "out")
            elif isinstance(t, Composite):
                threadport2element[key] = self.lookup(pointer)
            else:
                raise Exception("Composite '%s' assigns undefined '%s' to thread port '%s'."
                                % (composite.name, pointer, port.name))
        self.pop_scope()
        for key in threadport2element:
            self.env[key] = threadport2element[key]

    def allocate_resources(self):
        """
        Insert necessary elements for resource mapping and join elements. This method mutates self.graph
        """
        intersect = self.threads_api.intersection(self.threads_internal)
        if len(intersect) > 0:
            raise Exception("Element instance %s cannot be triggered by both internal and external triggers."
                            % intersect)
        t = ThreadAllocator(self.graph, self.threads_api, self.threads_internal, self.APIs)
        t.transform()
        self.graph.APIcode = t.APIcode