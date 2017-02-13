import re

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
        self.code = '  ' + code
        self.local_state = local_state
        self.state_params = state_params

        self.output_fire = None
        self.output_code = None

        self.analyze_output_type()
        #self.reorder_outports()

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.name == other.name and
                self.inports == other.inports and self.outports == other.outports and self.code == other.code and
                self.local_state == other.local_state and self.state_params == other.state_params)

    def count_ports_occurrence(self, code):
        occurrence = []
        for port in self.outports:
            occurrence.append((port.name, self.count_occurrence(code, port.name)))
        return occurrence

    def count_occurrence(self, code, name):
        code = code
        m = re.search('[^a-zA-Z0-9_]' + name + '[^a-zA-Z0-9_]', code)
        if m:
            return 1 + self.count_occurrence(code[m.end(0):], name)
        else:
            return 0

    def analyze_output_type(self):
        m = re.search('output[ ]*\{([^}]*)}', self.code)
        if m:
            # output { ... }
            self.output_fire = "all"
            program_code = self.code[:m.start(0)]
            out_code = ' ' + m.group(1)
            occurrence_out = self.count_ports_occurrence(out_code)

            for name, count in occurrence_out:
                if not count == 1:
                    raise Exception("Element '%s' must fire port '%s' exactly once, but it fires '%s' %d times."
                                    % (self.name, name, name, count))

            name2call = {}
            for port in self.outports:
                m = re.search('[^a-zA-Z0-9_](' + port.name + '[ ]*\([^)]*\))', out_code)
                name2call[port.name] = m.group(1)

            self.output_code = name2call

        else:
            m = re.search('output[ ]+switch[ ]*\{([^}]*)}', self.code)
            if m:
                # output switch { ... }
                program_code = self.code[:m.start(0)]
                out_code = self.code[m.start(1):m.end(1)]
                cases = out_code.split(';')
                re.search('^[ ]*$', cases[-1])
                if re.search('^[ ]*$', cases[-1]) is None:
                    raise Exception("Illegal form of output { ... } block in element '%s'." % self.name)
                count = {}
                cases = cases[:-1]

                m = re.search('^[ ]*else[ ]*:[ ]*([a-zA-Z0-9_]+)(\([^)]*\))[ ]*$', cases[-1])
                if m:
                    # has else
                    self.output_fire = "one"
                    count[m.group(1)] = 1
                    cases = cases[:-1]
                    else_expr = m.group(1) + m.group(2)
                else:
                    # no else
                    self.output_fire = "zero_or_one"
                    else_expr = None

                cases_exprs = []
                for case in cases:
                    m = re.search('^[ ]*case([^:]+):[ ]*([a-zA-Z0-9_]+)(\([^)]*\))[ ]*$', case)
                    if m:
                        cases_exprs.append((m.group(1), m.group(2) + m.group(3)))
                        if m.group(1) in count:
                            count[m.group(2)] += 1
                        else:
                            count[m.group(2)] = 1
                    else:
                        raise Exception("Illegal form of 'case' in the output block in element '%s': %s"
                                        % (self.name, case))
                if else_expr:
                    cases_exprs.append(("else", else_expr))

                for port in self.outports:
                    if port.name not in count:
                        raise Exception("Element '%s' never fire port '%s'." % (self.name, port.name))

                self.output_code = cases_exprs
            else:
                # no output area
                if len(self.outports) > 0:
                    raise Exception("Element '%s' does not have output { ... } block." % self.name)
                program_code = self.code

        # Check that it doesn't fire output port in program area.
        occurrence_program = self.count_ports_occurrence(program_code)
        for name, count in occurrence_program:
            if count > 0:
                raise Exception("Element '%s' fires port '%s' outside output { ... } block." % (self.name, name))

        self.code = program_code

    def get_output_code(self, order):
        src = ""
        if self.output_fire is None:
            if self.output_code:
                raise Exception("Element's output_fire is None, but its output_code is not None.")
            return src

        elif self.output_fire == "all":
            if len(order) == 0:
                for port in self.outports:
                    expr = self.output_code[port.name]
                    src += "  %s;\n" % expr
            elif len(order) == len(self.outports):
                for port_name in order:
                    expr = self.output_code[port_name]
                    src += "  %s;\n" % expr
            else:
                raise Exception("Element '%s' has %d output ports, but the order of ports only include %d ports."
                                % (self.name, len(self.outports), len(order)))
            return src

        else:
            cases_exprs = self.output_code
            if self.output_fire == "one":
                else_expr = cases_exprs[-1][1]
                cases_exprs = cases_exprs[:-1]
            else:
                else_expr = None

            src += self.generate_nested_if(cases_exprs, else_expr)
            return src

    def generate_nested_if(self, cases, else_expr):
        src = "  if(%s) %s;\n" % (cases[0][0], cases[0][1])
        for case_expr in cases[1:]:
            src += "  else if(%s) %s;\n" % (case_expr[0], case_expr[1])

        if else_expr:
            src += "  else %s;\n" % else_expr
        return src

    def reorder_outports(self):
        if len(self.outports) > 1:
            index2port = {}
            for port in self.outports:
                m = re.search('[^a-zA-Z0-9_]' + port.name + '[^a-zA-Z0-9_]', self.code)
                index2port[m.start(0)] = port

            keys = index2port.keys()
            keys.sort()
            ports = []
            for key in keys:
                ports.append(index2port[key])
            self.outports = ports


class ElementNode:
    def __init__(self, name, element, state_args):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to (element name, port)
        self.input2ele = {}    # map input port name to (element name, port)
        self.output2connect = {}
        self.state_args = state_args
        self.thread = None

        # Join information
        self.join_ports_same_thread = None
        self.join_state_create = []  # which join buffers need to be created
        self.join_func_params = []   # which join buffers need to be passed as params
        self.join_output2save = {}   # which output ports need to be saved into join buffers
        self.join_call = []          # = 1 if this node needs to invoke the join element instance
        self.join_partial_order = []

        # API information
        self.API_return = None        # which state this node needs to return
        self.API_return_from = None   # which output node the the return value comes form
        self.API_return_final = None  # mark that this node has to create the return state


    def __str__(self):
        return self.element.name + "::" + self.name + "---OUT[" + str(self.output2ele) + "]" + "---IN[" + str(self.input2ele) + "]"

    def connect_output_port(self, port, f, fport, overwrite):
        if (not overwrite) and (port in self.output2ele):
            raise ConflictConnection(
                "The output port '%s' of element instance '%s' cannot be connected to both element instances '%s' and '%s'."
                % (port, self.name, self.output2ele[port][0], f))
        self.output2ele[port] = (f, fport)

    def connect_input_port(self, port, f, fport):
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


class StateNode:
    def __init__(self, name, state, init):
        self.name = name
        self.state = state
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
        self.APIs = []

        # Inject and probe
        self.inject_populates = {}
        self.probe_compares = {}

    def __str__(self):
        s = "Graph:\n"
        # s += "  states: %s\n" % str(self.states)
        s += "  states: %s\n" % [str(self.state_instances[x].state) + "::" + x for x in self.state_instances.keys()]
        # s += "  elements: %s\n" % str(self.elements)
        # s += "  elements: %s\n" % [str(x) for x in self.instances.values()]
        s += "  elements:\n"
        for x in self.instances.values():
            s += "    " + str(x) + "\n"
        return s

    def is_state(self, state_name):
        return state_name in self.states

    def clear_APIs(self):
        self.APIs = []

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

    def newStateInstance(self, state, name, init=False):
        s = self.states[state]
        ret = StateNode(name, s, init)
        self.state_instances[name] = ret

    def newElementInstance(self, element, name, state_args=[]):
        if not element in self.elements:
            raise Exception("Element '%s' is undefined." % element)
        e = self.elements[element]
        ret = ElementNode(name, e, state_args)
        self.instances[name] = ret

        # Check state types
        if not (len(state_args) == len(e.state_params)):
            raise Exception("Element '%s' requires %d state arguments. %d states are given."
                            % (e.name, len(e.state_params), len(state_args)))
        for i in range(len(state_args)):
            (type, local_name) = e.state_params[i]
            s = state_args[i]
            state = self.state_instances[s].state
            if not (state.name == type):
                raise Exception("Element '%s' expects state '%s'. State '%s' is given." % (e.name, type, state.name))

        return ret

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
            assert len(e1.outports) == 1,\
                "Element instance '%s' has multiple output ports. Please specify which port to connect." % name1
            out1 = e1.outports[0].name
            out_argtypes += e1.outports[0].argtypes

        in_argtypes = []
        if in2:
            assert (in2 in [x.name for x in e2.inports]), \
                "Port '%s' is undefined for element '%s'. Available ports are %s." \
                % (in2, name2, [x.name for x in e2.inports])
            in_argtypes += [x for x in e2.inports if x.name == in2][0].argtypes
        else:
            # If not specified, concat all ports together.
            if len(e2.inports) == 1:
                in2 = e2.inports[0].name
            else:
                in2 = [port.name for port in e2.inports]
            in_argtypes += sum([port.argtypes for port in e2.inports], []) # Flatten a list of list

        # Check types
        if not(in_argtypes == out_argtypes):
            if out1 and in2:
                raise Exception("Mismatched ports -- output port '%s' of element '%s' and input port '%s' of element '%s': %s vs %s"
                                % (out1, name1, in2, name2, out_argtypes, in_argtypes))
            else:
                raise Exception("Mismatched ports -- output port of element '%s' and input port of element '%s': %s vs %s"
                                % (name1, name2, out_argtypes, in_argtypes))

        i1.connect_output_port(out1, i2.name, in2, overwrite)
        if isinstance(in2, str):
            i2.connect_input_port(in2, i1.name, out1)
        else:
            for port_name in in2:
                i2.connect_input_port(port_name, i1.name, out1)

    def get_identity_element(self, argtypes):
        name = "_identity_" + "_".join(argtypes)

        if name in self.identity:
            return self.identity[name]

        args = []
        types_args = []
        for i in range(len(argtypes)):
            arg = "arg%d" % i
            args.append(arg)
            types_args.append("%s %s" % (argtypes[i], arg))

        src = "(%s) = in(); output { out(%s); }\n" % (", ".join(types_args), ", ".join(args))

        e = Element(name,
                    [Port("in", argtypes)],
                    [Port("out", argtypes)],
                    src)

        self.identity[name] = e
        return e

    def check_input_ports(self):
        for instance in self.instances.values():
            instance.check_input_ports()
