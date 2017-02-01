import sys

class UndefinedInstance(Exception):
    pass

class UndefinedPort(Exception):
    pass

class ConflictConnection(Exception):
    pass

class RedefineError(Exception):
    pass

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

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.name == other.name and
                self.inports == other.inports and self.outports == other.outports and self.code == other.code and
                self.local_state == other.local_state and self.state_params == other.state_params)


class ElementNode:
    def __init__(self, name, element, state_args):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to (element name, port)
        self.input2ele = {}    # map input port name to (element name, port)
        self.output2connect = {}
        self.state_args = state_args
        self.thread = None

    def __str__(self):
        return self.element.name + "::" + self.name + "[" + str(self.output2ele) + "]"

    def connect_output_port(self, port, f, fport, overwrite):
        if (not overwrite) and (port in self.output2ele):
            raise ConflictConnection(
                "The output port '%s' of element instance '%s' cannot be connected to both element instances '%s' and '%s'."
                % (port, self.name, self.output2ele[port][0], f))
        self.output2ele[port] = (f, fport)

    def connect_input_port(self, port, f, fport, overwrite):
        if not overwrite:
            if port in self.input2ele:
                self.input2ele[port].append((f, fport))
            else:
                self.input2ele[port] = [(f, fport)]

    def check_input_ports(self):
        if len(self.input2ele) > 1:
            for port in self.input2ele:
                port_list = self.input2ele[port]
                if len(port_list) > 1:
                    raise ConflictConnection(
                        "The input port '%s' of element instance '%s' cannot be connected to multiple element instances %s because '%s' is a join element."
                        % (port, self.name, [x[0] for x in port_list], self.name))

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

    def __eq__(self, other):
        #print "Port.eq", self, other, (self.__class__ == other.__class__ and self.name == other.name and self.argtypes == other.argtypes)
        return self.__class__ == other.__class__ and self.name == other.name and self.argtypes == other.argtypes


class State:
    def __init__(self, name, content, init=None):
        self.name = name
        self.content = content
        self.init = init

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.name == other.name and self.content == other.content and self.init == other.init)

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
        self.APIcode = None

    def __str__(self):
        s = "Graph:\n"
        # s += "  states: %s\n" % str(self.states)
        s += "  states: %s\n" % [str(self.state_instances[x]) + "::" + x for x in self.state_instances.keys()]
        # s += "  elements: %s\n" % str(self.elements)
        # s += "  elements: %s\n" % [str(x) for x in self.instances.values()]
        s += "  elements:\n"
        for x in self.instances.values():
            s += "    " + str(x) + "\n"
        return s

    def has_element_instance(self, instance_name):
        return instance_name in self.instances

    def get_inport_argtypes(self, instance_name, port_name):
        try:
            inports = self.instances[instance_name].element.inports
            return [x for x in inports if x.name == port_name][0].argtypes
        except IndexError:
            raise UndefinedPort()
        except KeyError:
            raise UndefinedInstance()

    def get_outport_argtypes(self, instance_name, port_name):
        try:
            outports = self.instances[instance_name].element.outports
            return [x for x in outports if x.name == port_name][0].argtypes
        except IndexError:
            raise UndefinedPort()
        except KeyError:
            raise UndefinedInstance()

    def addState(self,state):
        if state.name in self.states:
            if not self.states[state.name] == state:
                raise RedefineError("State '%s' is already defined." % state.name)
            return False
        else:
            self.states[state.name] = state
            return True

    def addElement(self,element):
        if element.name in self.elements:
            if not self.elements[element.name] == element:
                raise RedefineError("Element '%s' is already defined." % element.name)
            return False
        else:
            self.elements[element.name] = element
            return True

    def newStateInstance(self, state, name):
        s = self.states[state]
        self.state_instances[name] = s

    def newElementInstance(self, element, name, state_args=[]):
        if not element in self.elements:
            raise Exception("Element '%s' is undefined." % element)
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

    def connect(self, name1, name2, out1=None, in2=None, overwrite=False):
        i1 = self.instances[name1]
        i2 = self.instances[name2]
        e1 = i1.element
        e2 = i2.element

        out_argtypes = []
        if out1:
            assert (out1 in [x.name for x in e1.outports]), \
                "Port '%s' is undefined for element '%s'. Available ports are %s." \
                % (out1, name1, [x.name for x in e1.outports])
            out_argtypes += [x for x in e1.outports if x.name == out1][0].argtypes
        else:
            assert (len(e1.outports) == 1)
            out1 = e1.outports[0].name
            out_argtypes += e1.outports[0].argtypes

        in_argtypes = []
        if in2:
            assert (in2 in [x.name for x in e2.inports]), \
                "Port '%s' is undefined for element '%s'. Available ports are %s." \
                % (in2, name2, [x.name for x in e2.inports])
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

        i1.connect_output_port(out1, i2.name, in2, overwrite)
        i2.connect_input_port(in2, i1.name, out1, overwrite)

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

    def check_input_ports(self):
        for instance in self.instances.values():
            instance.check_input_ports()
