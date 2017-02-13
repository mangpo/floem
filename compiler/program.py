from standard_elements import *
from thread_allocation import *


class StateInstance:
    def __init__(self, state, name, init=False):
        self.state = state
        self.name = name
        self.init = init


class ElementInstance:
    def __init__(self, element, name, args=[]):
        if not isinstance(args, list):
            raise TypeError("State arguments of element instance '%s' is not a list of states." % name)
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
    def __init__(self, *statements):
        self.statements = statements


class Spec:
    def __init__(self, *statements):
        self.statements = statements


class Impl:
    def __init__(self, *statements):
        self.statements = statements


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


class Inject:
    def __init__(self, type, name, size, func):
        self.type = type
        self.name = name
        self.size = size
        self.func = func


class Probe:
    def __init__(self, type, name, size, func):
        self.type = type
        self.name = name
        self.size = size
        self.func = func


class StorageState:
    def __init__(self, name, state_instance, state, type, size, func):
        self.name = name
        self.state_instance = state_instance
        self.state = state
        self.type = type
        self.size = size
        self.func = func
        self.spec_instances = {}
        self.impl_instances = {}

    def add(self, instance):
        m = re.match('_spec_(.+)', instance)
        if m:
            self.spec_instances[m.group(1)] = instance
        m = re.match('_impl_(.+)', instance)
        if m:
            self.impl_instances[m.group(1)] = instance


class PopulateState(StorageState):
    def __init__(self, name, state_instance, state, type, size, func):
        StorageState.__init__(self, name, state_instance, state, type, size, func)

    def clone(self):
        return PopulateState(self.name, self.state_instance, self.state, self.type, self.size, self.func)


class CompareState(StorageState):
    def __init__(self, name, state_instance, state, type, size, func):
        StorageState.__init__(self, name, state_instance, state, type, size, func)

    def clone(self):
        return CompareState(self.name, self.state_instance, self.state, self.type, self.size, self.func)


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
        self.new_state_type = False


class GraphGenerator:
    def __init__(self):
        self.graph = Graph()
        self.composites = {}
        self.elements = {}
        self.env = {}

        self.threads_api = set()
        self.threads_internal = set()

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
            return self.lookup_recursive(table["__up__"], key)
        else:
            raise Exception("'%s' is undefined." % str(key))

    def put_state(self, used_name, type, real_name):
        self.env[used_name] = (type, real_name)

    def get_state_name(self, name):
        return self.lookup(name)[1]

    def get_state_type(self, name):
        return self.lookup(name)[0]

    def put_instance(self, local_name, stack, element):
        self.env[local_name] = (stack, element)

    def get_instance_stack(self, name):
        return self.lookup(name)[0]

    def get_instance_type(self, name):
        return self.lookup(name)[1]

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
            global_name = get_node_name(stack, x.name)
            try:
                self.put_instance(x.name, stack, self.elements[x.element])
            except KeyError:
                raise Exception("Element '%s' is undefined." % x.element)
            self.graph.newElementInstance(x.element, global_name,
                                          [self.get_state_name(arg) for arg in x.args])
        elif isinstance(x, StateInstance):
            new_name = get_node_name(stack, x.name)
            if x.name in self.graph.inject_populates:
                self.graph.inject_populates[x.name].add(new_name)
            if x.name in self.graph.probe_compares:
                self.graph.probe_compares[x.name].add(new_name)
            self.put_state(x.name, x.state, new_name)
            self.graph.newStateInstance(x.state, new_name, x.init)
        elif isinstance(x, Connect):
            self.interpret_Connect(x)
        elif isinstance(x, Composite):
            self.composites[x.name] = x
        elif isinstance(x, CompositeInstance):
            try:
                self.put_instance(x.name, stack, self.composites[x.element])
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
            self.graph.APIs.append(APIFunction(x.name, call_instance, call_port, return_instance, return_port,
                                               x.state_name))
        elif isinstance(x, PopulateState):
            self.graph.inject_populates[x.state_instance] = x.clone()
        elif isinstance(x, CompareState):
            self.graph.probe_compares[x.state_instance] = x.clone()
        elif isinstance(x, InjectAndProbe):
            self.interpret_InjectAndProbe(x, stack)
        else:
            raise Exception("GraphGenerator: unimplemented for %s." % x)

    def interpret_InjectAndProbe(self, x, stack):
        state_name = "_" + x.probe + "State"
        state = ProbeState(state_name, x.type, x.storage_size)
        inject = InjectElement(x.inject, x.type)
        probe = ProbeElement(x.probe, x.type, state_name, x.storage_size)
        self.graph.addState(state)
        self.graph.addElement(inject)
        self.graph.addElement(probe)

        # state instance
        new_name = get_node_name(stack, x.state_instance_name)
        self.put_state(x.state_instance_name, state_name, new_name)
        self.graph.newStateInstance(state_name, new_name)

        # element instance
        self.put_instance(x.inject, stack, inject)
        self.graph.newElementInstance(x.inject, get_node_name(stack, x.inject))
        for i in range(x.n):
            probe_name = x.probe + str(i + 1)
            self.put_instance(probe_name, stack, probe)
            self.graph.newElementInstance(x.probe, get_node_name(stack, probe_name),
                                          [self.get_state_name(x.state_instance_name)])

    def interpret_Connect(self, x):
        (name1, out1) = self.adjust_connection(x.ele1, x.out1, "output")
        (name2, in2) = self.adjust_connection(x.ele2, x.in2, "input")
        stack1 = self.get_instance_stack(x.ele1)
        stack2 = self.get_instance_stack(x.ele2)
        self.graph.connect(get_node_name(stack1, name1), get_node_name(stack2, name2), out1, in2)

    def convert_to_element_ports(self, call_instance, call_ports, stack):
        """
        Convert to (element, ports)
        :param call_instance: element or composite instance
        :param call_ports: element or composite ports
        :param stack: program scope
        :return: (element, ports)
        """
        self.current_scope(call_instance, "APIFunction")
        t = self.get_instance_type(call_instance)
        if isinstance(t, Element):
            call_instance = get_node_name(stack, call_instance)
            return call_instance, call_ports
        elif isinstance(t, Composite):
            call_instance, call_ports = self.lookup((call_instance, call_ports))
            return call_instance, call_ports

    def adjust_connection(self, ele_name, port_name, type):
        t = self.get_instance_type(ele_name)
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
            is_composite = isinstance(self.get_instance_type(internal_name), Composite)
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
            is_composite = isinstance(self.get_instance_type(internal_name), Composite)
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
        port2element = dict()
        for port in composite.thread_ports + composite.inports + composite.outports:
            key = (x.name, port.name)
            pointer = port.argtypes
            if not isinstance(pointer, tuple) or not len(pointer) == 2:
                raise Exception("Port '%s' of composite '%s' should assign to a tuple of (name, port)."
                                % (port.name, composite.name))
            t = self.get_instance_type(pointer[0])
            if isinstance(t, Element):
                if port in composite.thread_ports:
                    port2element[key] = (get_node_name(new_stack, pointer[0]), pointer[1])
                elif port in composite.inports:
                    port2element[key] = (get_node_name(stack, x.name + "_" + port.name), "in")
                elif port in composite.outports:
                    port2element[key] = (get_node_name(stack, x.name + "_" + port.name), "out")
            elif isinstance(t, Composite):
                port2element[key] = self.lookup(pointer)
            else:
                raise Exception("Composite '%s' assigns undefined '%s' to thread port '%s'."
                                % (composite.name, pointer, port.name))
        self.pop_scope()
        for key in port2element:
            self.env[key] = port2element[key]

    def allocate_resources(self):
        """
        Insert necessary elements for resource mapping and join elements. This method mutates self.graph
        """
        intersect = self.threads_api.intersection(self.threads_internal)
        if len(intersect) > 0:
            raise Exception("Element instance %s cannot be triggered by both internal and external triggers."
                            % intersect)
        t = ThreadAllocator(self.graph, self.threads_api, self.threads_internal)
        t.transform()