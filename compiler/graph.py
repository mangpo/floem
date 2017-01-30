class Element:

    def __init__(self, name, inports, outports, code, local_state=None, state_params=[]):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = code
        self.local_state = local_state
        self.state_params = state_params

    def __str__(self):
        return self.name


class ElementNode:
    def __init__(self, name, element, state_args):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to (element name, port)
        self.output2connect = {}
        self.state_args = state_args
        self.thread = None

    def connectPort(self, port, f, fport):
        self.output2ele[port] = (f, fport)

    def __str__(self):
        return self.element.name + "::" + self.name + "[" + str(self.output2ele) + "]"

    def print_details(self):
        print "Element {"
        print "  type:", self.element.name, "| name:", self.name
        if self.thread:
            print "  thread:", self.thread
        print "  out-port:", self.output2ele
        if len(self.output2connect.keys()) > 0:
            print "  mark:", self.output2connect
        print "}"


class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes

    def __str__(self):
        return self.name


class State:
    def __init__(self, name, content, init=None):
        self.name = name
        self.content = content
        self.init = init


class Graph:
    def __init__(self, elements=[], states=[]):
        self.elements = {}
        self.instances = {}
        self.states = {}
        self.state_instances = {}
        for e in elements:
            self.elements[e.name] = e
        for s in states:
            self.states[s.name] = s

        self.identity = {}

    def __str__(self):
        s = "Graph:\n"
        # s += "  states: %s\n" % str(self.states)
        s += "  states: %s\n" % str(self.state_instances.values())
        # s += "  elements: %s\n" % str(self.elements)
        # s += "  elements: %s\n" % [str(x) for x in self.instances.values()]
        s += "  elements:\n"
        for x in self.instances.values():
            s += "    " + str(x) + "\n"
        return s

    def get_inport_argtypes(self, instance_name, port_name):
        inports = self.instances[instance_name].element.inports
        return [x for x in inports if x.name == port_name][0].argtypes

    def get_outport_argtypes(self, instance_name, port_name):
        outports = self.instances[instance_name].element.outports
        return [x for x in outports if x.name == port_name][0].argtypes

    def addState(self,state):
        self.states[state.name] = state

    def addElement(self,element):
        self.elements[element.name] = element

    def newStateInstance(self, state, name):
        s = self.states[state]
        self.state_instances[name] = s

    def newElementInstance(self, element, name, state_args=[]):
        e = self.elements[element]
        self.instances[name] = ElementNode(name, e, state_args)

        # Check state types
        if not (len(state_args) == len(e.state_params)):
            raise Exception("Element '%s' requires %d state arguments. %d states are given."
                            % (e.name, len(e.state_params), len(state_args)))
        for i in range(len(state_args)):
            (type, local_name) = e.state_params[i]
            s = state_args[i]
            state = self.state_instances[s]
            if not (state.name == type):
                raise Exception("Element '%s' expects state '%s'. State '%s' is given." % (e.name, type, state.name))

    def connect(self, name1, name2, out1=None, in2=None):
        i1 = self.instances[name1]
        i2 = self.instances[name2]
        e1 = i1.element
        e2 = i2.element

        out_argtypes = []
        if out1:
            assert (out1 in [x.name for x in e1.outports]), \
                "Port '%s' is undefined. Aviable ports are %s." \
                % (out1, [x.name for x in e1.outports])
            out_argtypes += [x for x in e1.outports if x.name == out1][0].argtypes
        else:
            assert (len(e1.outports) == 1)
            out1 = e1.outports[0].name
            out_argtypes += e1.outports[0].argtypes

        in_argtypes = []
        if in2:
            assert (in2 in [x.name for x in e2.inports]), \
                "Port '%s' is undefined. Aviable ports are %s." \
                % (in2, [x.name for x in e2.inports])
            in_argtypes += [x for x in e2.inports if x.name == in2][0].argtypes
        else:
            # assert (len(e2.inports) == 1)
            # Leave in2 = None if there is only one port.
            # If not specified, concat all ports together.
            in2 = e2.inports[0].name
            in_argtypes += sum([port.argtypes for port in e2.inports], []) # Flatten a list of list

        # Check types
        if not(in_argtypes == out_argtypes):
            if out1 and in2:
                raise Exception("Mismatched ports -- output port '%s' of element '%s' and input port '%s' of element '%s'"
                                % (out1, name1, in2, name2))
            else:
                raise Exception("Mismatched ports -- output port of element '%s' and input port of element '%s'"
                                % (name1, name2))

        i1.connectPort(out1, i2.name, in2)

    def get_identity_element(self, argtypes):
        name = "_identity_" + "_".join(argtypes)

        if name in self.identity:
            return self.identity[name]

        e = Element(name,
                    [Port("in", argtypes)],
                    [Port("out", argtypes)],
                    r'''out(in());''') # TODO

        self.identity[name] = e
        return e