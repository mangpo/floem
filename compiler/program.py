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

    def __str__(self):
        return self.name + '<' + self.element + '>'


class Connect:
    def __init__(self, ele1, ele2, out1=None, in2=None):
        assert isinstance(ele1, str)
        self.ele1 = ele1
        self.ele2 = ele2
        self.out1 = out1
        self.in2 = in2

    def __str__(self):
        return self.ele1 + "-->" + self.ele2


class Program:
    def __init__(self, *statements):
        self.statements = list(statements)


class Spec:
    def __init__(self, statements):
        self.statements = statements


class Impl:
    def __init__(self, statements):
        self.statements = statements


class Composite:
    def __init__(self, name, program):
        self.name = name
        self.program = program


class CompositeInstance:
    def __init__(self, element, name, args=[]):
        self.element = element
        self.name = name
        self.args = args


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
        else:
            m = re.match('_impl_(.+)', instance)
            if m:
                self.impl_instances[m.group(1)] = instance
            else:
                self.spec_instances[instance] = instance


class PopulateState(StorageState):
    def __init__(self, name, state_instance, state, type, size, func):
        StorageState.__init__(self, name, state_instance, state, type, size, func)
        self.spec_ele_instances = []
        self.impl_ele_instances = []

    def clone(self):
        return PopulateState(self.name, self.state_instance, self.state, self.type, self.size, self.func)

    def add_element_instance(self, instance):
        m = re.match('_spec_(.+)', instance)
        if m:
            self.spec_ele_instances.append(instance)
        else:
            m = re.match('_impl_(.+)', instance)
            if m:
                self.impl_ele_instances.append(instance)
            else:
                self.spec_ele_instances.append(instance)


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
    def __init__(self, name, call_types, return_type, default_val=None):
        assert isinstance(call_types, list), \
            ("call_types argument of APIFunction should be a list of types. '%s' is given." % call_types)
        assert (return_type is None or isinstance(return_type, str)), \
            ("return_type argument of APIFunction should be a data type in string format. '%s' is given." % return_type)
        self.name = name
        self.call_types = [common.sanitize_type(t) for t in call_types]
        self.return_type = common.sanitize_type(return_type)
        self.default_val = default_val
        self.call_instance = None
        self.return_instance = None
        self.return_port = None
        self.process = None


class InternalTrigger:
    def __init__(self, name):
        self.name = name
        self.call_instance = None


class ResourceMap:
    def __init__(self, resource, instance):
        self.resource = resource
        self.instance = instance

    def __str__(self):
        return self.instance + "@" + self.resource


class ResourceOrder:
    def __init__(self, a, b):
        self.a = a
        self.b = b


class ProcessMap:
    def __init__(self, process, thread):
        self.process = process
        self.thread = thread

    def __str__(self):
        return self.thread + "@" + self.process


class GraphGenerator:
    def __init__(self, default_process):
        self.graph = Graph(default_process)
        self.composites = {}
        self.elements = {}
        self.env = {}

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
            return None

    def put_state(self, used_name, type, real_name):
        if used_name in self.env:
            raise Exception("'%s' has already been defined in the current scope." % used_name)
        self.env[used_name] = (type, real_name)

    def get_state_name(self, name):
        return self.lookup(name)[1]

    def get_state_type(self, name):
        return self.lookup(name)[0]

    def put_instance(self, local_name, stack, element):
        if local_name in self.env:
            raise Exception("'%s' has already been defined in the current scope." % local_name)
        self.env[local_name] = (stack, element)

    def get_instance_stack(self, name):
        return self.lookup(name)[0]

    def get_instance_type(self, name):
        return self.lookup(name)[1]

    def put_resource(self, local_name, global_name):
        if local_name in self.env:
            raise Exception("'%s' has already been defined in the current scope." % local_name)
        self.env[local_name] = global_name

    def get_resource(self, local_name):
        return self.lookup(local_name)

    def push_scope(self):
        env = dict()
        env["__up__"] = self.env
        self.env = env

    def pop_scope(self):
        self.env = self.env["__up__"]

    def current_scope(self, name, construct):
        if name not in self.env:
            raise Exception("Instance '%s' must be defined in the same local scope as '%s' command."
                            % (name, construct))

    def get_element_instance_name(self, trigger):
        t = self.get_instance_type(trigger.element_instance)
        if isinstance(t, Element):
            new_name = get_node_name(self.get_instance_stack(trigger.element_instance), trigger.element_instance)
        else:
            new_name, port = self.lookup((trigger.element_instance, trigger.port))

        return new_name

    def adjust_init(self, init):
        if isinstance(init, str):
            state_type_name = self.lookup(init)
            if state_type_name:
                return state_type_name[1]
            return init
        elif isinstance(init, AddressOf):
            return AddressOf(self.adjust_init(init.of))
        elif isinstance(init, list):
            ret = []
            for x in init:
                ret.append(self.adjust_init(x))
            return ret
        else:
            return init

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
            new_name = get_node_name(stack, x.name)
            # Collect inject information
            if len(x.args) == 1 and x.args[0] in self.graph.inject_populates:
                self.graph.inject_populates[x.args[0]].add_element_instance(new_name)
            try:
                self.put_instance(x.name, stack, self.elements[x.element])
            except KeyError:
                raise Exception("Element '%s' is undefined." % x.element)
            self.graph.newElementInstance(x.element, new_name,
                                          [self.get_state_name(arg) for arg in x.args])
        elif isinstance(x, StateInstance):
            new_name = get_node_name(stack, x.name)
            # Collect inject information
            if x.name in self.graph.inject_populates:
                self.graph.inject_populates[x.name].add(new_name)
            if x.name in self.graph.probe_compares:
                self.graph.probe_compares[x.name].add(new_name)
            self.put_state(x.name, x.state, new_name)
            self.graph.newStateInstance(x.state, new_name, self.adjust_init(x.init))
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
            global_name = get_node_name(stack, x.name)
            self.put_resource(x.name, global_name)
            self.graph.threads_internal.append(InternalTrigger(global_name))

        elif isinstance(x, APIFunction):
            #global_name = get_node_name(stack, x.name)
            global_name = x.name
            self.put_resource(x.name, global_name)
            self.graph.threads_API.append(APIFunction(x.name, x.call_types, x.return_type, x.default_val))

        elif isinstance(x, ResourceMap):
            inst_name = get_node_name(self.get_instance_stack(x.instance), x.instance)
            resource_name = self.get_resource(x.resource)
            instance = self.graph.instances[inst_name]
            if instance.thread and resource_name is not instance.thread:
                raise Exception("Element instance '%s' cannot be mapped to both '%s' and '%s'."
                                % (x.instance, instance.thread, resource_name))
            instance.thread = resource_name

        elif isinstance(x, ResourceOrder):
            a_name = get_node_name(self.get_instance_stack(x.a), x.a)
            b_name = get_node_name(self.get_instance_stack(x.b), x.b)
            self.graph.threads_order.append((a_name, b_name))

        elif isinstance(x, ProcessMap):
            self.graph.thread2process[x.thread] = x.process

        elif isinstance(x, PopulateState):
            self.graph.inject_populates[x.state_instance] = x.clone()
        elif isinstance(x, CompareState):
            self.graph.probe_compares[x.state_instance] = x.clone()
        else:
            raise Exception("GraphGenerator: unimplemented for %s." % x)

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
        self.push_scope()
        self.interpret(composite.program, new_stack)
        self.pop_scope()

    def allocate_resources(self):
        """
        Insert necessary elements for resource mapping and join elements. This method mutates self.graph
        """
        t = ThreadAllocator(self.graph)
        t.transform()
