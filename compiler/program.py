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

        self.threads_api = set()
        self.threads_internal = set()

    @staticmethod
    def get_node_name(stack, name):
        if len(stack) > 0:
            return "_" + "_".join(stack) + "_" + name
        else:
            return name

    def interpret(self, x, stack=[]):
        if isinstance(x, Program):
            for s in x.statements:
                self.interpret(s, stack)
        elif isinstance(x, Element):
            self.graph.addElement(x)
        elif isinstance(x, State):
            self.graph.addState(x)
        elif isinstance(x, ElementInstance):
            self.graph.newElementInstance(x.element, self.get_node_name(stack,x.name), x.args)
        elif isinstance(x, StateInstance):
            self.graph.newStateInstance(x.state, self.get_node_name(stack, x.name))
        elif isinstance(x, Connect):
            self.interpret_Connect(x, stack)
        elif isinstance(x, Composite):
            self.composites[x.name] = x
        elif isinstance(x, CompositeInstance):
            self.interpret_CompositeInstance(x, stack)
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
        self.interpret(composite.program, new_stack)

        # Create element instances for input ports, and connect the interface elements to internal elements.
        for port in composite.inports:
            portname = port.name
            (internal_name, internal_port) = port.argtypes
            argtypes = self.graph.get_inport_argtypes(self.get_node_name(new_stack, internal_name), internal_port)
            ele = self.graph.get_identity_element(argtypes)
            instance_name = x.name + "_" + portname
            self.graph.addElement(ele)
            self.graph.newElementInstance(ele.name, instance_name)
            self.graph.connect(self.get_node_name(stack, instance_name), self.get_node_name(new_stack, internal_name),
                               None, internal_port)

        # Create element instances for output ports, and connect the interface elements to internal elements.
        for port in composite.outports:
            portname = port.name
            (internal_name, internal_port) = port.argtypes
            argtypes = self.graph.get_outport_argtypes(self.get_node_name(new_stack, internal_name), internal_port)
            ele = self.graph.get_identity_element(argtypes)
            instance_name = x.name + "_" + portname
            self.graph.addElement(ele)
            self.graph.newElementInstance(ele.name, instance_name)
            self.graph.connect(self.get_node_name(new_stack, internal_name), self.get_node_name(stack, instance_name),
                               internal_port, None)

    def allocate_resources(self):
        """
        Insert necessary elements for resource mapping and join elements. This method mutates self.graph
        """
        t = ThreadAllocator(self.graph, self.threads_api, self.threads_internal)
        t.transform()
