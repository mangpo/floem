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

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.name == other.name and self.element == other.element


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
    def __init__(self, name, state_instance, state, type, size, func, interval):
        StorageState.__init__(self, name, state_instance, state, type, size, func)
        self.spec_ele_instances = []
        self.impl_ele_instances = []
        self.interval = interval

    def clone(self):
        return PopulateState(self.name, self.state_instance, self.state, self.type, self.size, self.func, self.interval)

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

def get_resource_name(stack, name):
    if len(stack) > 0:
        if stack[0] == 'impl':
            return name
        else:
            return get_node_name(stack, name)
    else:
        return name

class APIFunction:
    def __init__(self, name, call_types, return_type, default_val=None, output_elements=[]):
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
        self.output_elements = output_elements


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


class DeviceMap:
    def __init__(self, device, thread, cores=[0]):
        self.device = device
        self.thread = thread
        self.cores = cores


class MasterProcess:
    def __init__(self, master):
        self.master = master


class PipelineState:
    def __init__(self, start_instance, state):
        self.start_instance = start_instance
        self.state = state


class StartWithCoreID:
    def __init__(self, instance):
        self.instance = instance


class GraphGenerator:
    def __init__(self, default_process, original=None):
        self.graph = Graph(default_process, original)
        self.composites = {}
        self.elements = {}

    # def check_composite_port(self, composite_name, port_name, port_value):
    #     if not len(port_value) == 2:
    #         raise TypeError("The value of port '%s' of composite '%s' should be a pair of (internal instance, port)." %
    #                         (port_name, composite_name))

    def adjust_init(self, stack, init):
        if isinstance(init, str):
            name = get_node_name(stack, init)
            if name in self.graph.state_instances:
                return name
            return init
        elif isinstance(init, AddressOf):
            return AddressOf(self.adjust_init(stack, init.of))
        elif isinstance(init, list):
            ret = []
            for x in init:
                ret.append(self.adjust_init(stack, x))
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
        elif isinstance(x, MemoryRegion):
            self.graph.addMemoryRegion(x)
        elif isinstance(x, ElementInstance):
            new_name = get_node_name(stack, x.name)
            # Collect inject information
            if len(x.args) == 1 and x.args[0] in self.graph.inject_populates:
                self.graph.inject_populates[x.args[0]].add_element_instance(new_name)
            self.graph.newElementInstance(x.element, new_name,
                                          [get_node_name(stack, arg) for arg in x.args], x)
        elif isinstance(x, StateInstance):
            new_name = get_node_name(stack, x.name)
            # Collect inject information
            if x.name in self.graph.inject_populates:
                self.graph.inject_populates[x.name].add(new_name)
            if x.name in self.graph.probe_compares:
                self.graph.probe_compares[x.name].add(new_name)
            self.graph.newStateInstance(x.state, new_name, self.adjust_init(stack, x.init))
        elif isinstance(x, Connect):
            self.graph.connect(get_node_name(stack, x.ele1), get_node_name(stack, x.ele2), x.out1, x.in2)
        elif isinstance(x, Composite):
            self.composites[x.name] = x
        elif isinstance(x, CompositeInstance):
            self.interpret_CompositeInstance(x, stack)

        elif isinstance(x, InternalTrigger):
            global_name = get_resource_name(stack, x.name)
            self.graph.threads_internal.append(InternalTrigger(global_name))

        elif isinstance(x, APIFunction):
            global_name = get_resource_name(stack, x.name)
            #global_name = x.name
            if x.output_elements:
                for inst in x.output_elements:
                    new_name = get_node_name(stack, inst.name)
                    self.graph.API_outputs.append(new_name)
            self.graph.threads_API.append(APIFunction(global_name, x.call_types, x.return_type, x.default_val))

        elif isinstance(x, ResourceMap):
            inst_name = get_node_name(stack, x.instance)
            resource_name = get_resource_name(stack, x.resource)
            instance = self.graph.instances[inst_name]
            if instance.thread and (not (resource_name == instance.thread)) and (not instance.element.special):
                raise Exception("Element instance '%s' cannot be mapped to both '%s' and '%s'."
                                % (x.instance, instance.thread, resource_name))
            instance.thread = resource_name

        elif isinstance(x, ResourceOrder):
            if isinstance(x.a, str):
                a_name = get_resource_name(stack, x.a)
            elif isinstance(x.a, list):
                a_name = []
                for a in x.a:
                    a_name.append(get_resource_name(stack, a))
            b_name = get_resource_name(stack, x.b)
            self.graph.threads_order.append((a_name, b_name))

        elif isinstance(x, ProcessMap):
            self.graph.thread2process[get_resource_name(stack,x.thread)] = x.process

        elif isinstance(x, DeviceMap):
            self.graph.thread2device[get_resource_name(stack,x.thread)] = (x.device, x.cores)

        elif isinstance(x, MasterProcess):
            self.graph.master_process = x.master

        elif isinstance(x, PipelineState):
            inst_name = get_node_name(stack, x.start_instance)
            self.graph.add_pipeline_state(inst_name, x.state)

        elif isinstance(x, PopulateState):
            self.graph.inject_populates[x.state_instance] = x.clone()
        elif isinstance(x, CompareState):
            self.graph.probe_compares[x.state_instance] = x.clone()

        elif isinstance(x, StartWithCoreID):
            self.graph.instances[x.instance].core_id = True
        else:
            raise Exception("GraphGenerator: unimplemented for %s." % x)

    def interpret_CompositeInstance(self, x, stack):
        new_stack = stack + [x.name]
        composite = self.composites[x.element]
        self.interpret(composite.program, new_stack)


def program_to_graph_pass(program, default_process="tmp", original=None):
    # Generate data-flow graph.
    gen = GraphGenerator(default_process, original=original)
    gen.interpret(program)
    return gen.graph