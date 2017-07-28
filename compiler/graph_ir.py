import copy, re
import target, common


class UndefinedInstance(Exception):
    pass

class UndefinedPort(Exception):
    pass

class ConflictConnection(Exception):
    pass

class RedefineError(Exception):
    pass

def remove_comment(code):
    m = re.search("//[^\n]*\n", code)
    if m:
        return remove_comment(code[:m.start(0)] + code[m.end(0):])
    else:
        m = re.search("/\*[^\*]*\*/", code)
        if m:
            return remove_comment(code[:m.start(0)] + code[m.end(0):])
        else:
            return code


class Element:

    def __init__(self, name, inports, outports, code, state_params=[], analyze=True, code_cavium=None):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = '  ' + remove_comment(code)
        if code_cavium:
            code_cavium = '  ' + remove_comment(code_cavium)
        self.code_cavium = code_cavium
        self.cleanup = ''
        self.state_params = state_params

        self.output_fire = None
        self.output_code = None
        self.output_code_cavium = None

        self.special = None
        self.defs = set()
        self.uses = set()

        if analyze:
            self.check_ports(inports + outports)
            self.analyze_output_type()

    def clone(self, new_name):
        e = Element(new_name, [x.clone() for x in self.inports], [x.clone() for x in self.outports], self.code,
                    self.state_params, False, code_cavium=self.code_cavium)
        e.output_fire = self.output_fire
        e.output_code = copy.copy(self.output_code)
        e.output_code_cavium = copy.copy(self.output_code_cavium)
        e.cleanup = self.cleanup
        e.special = self.special
        return e

    def number_of_args(self):
        n = 0
        for port in self.inports:
            n += len(port.argtypes)
        return n

    def check_ports(self, ports):
        names = []
        for port in ports:
            if port.name in names:
                raise Exception("Element '%s' has multiple '%s' ports." % (self.name, port.name))
            names.append(port.name)

    def add_empty_outports(self, port_names):
        assert self.output_fire == "all", ("Cannot add ports too an  '%s' whose output_fires != all." % self.name)
        self.outports += [Port(name, []) for name in port_names]
        for name in port_names:
            self.output_code[name] = name + "()"
        if self.output_code_cavium:
            for name in port_names:
                self.output_code_cavium[name] = name + "()"

    def add_empty_inports(self, port_names):
        self.inports += [Port(name, []) for name in port_names]
        # for name in port_names:
        #     self.code = ("%s();\n" % name) + self.code

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.name == other.name and
                self.inports == other.inports and self.outports == other.outports and self.code == other.code and
                self.state_params == other.state_params)

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
        self.code, self.output_code, self.output_fire = self.analyze_output_type_internal(self.code)
        if self.code_cavium is not None:
            code, output_code, output_fire = self.analyze_output_type_internal(self.code_cavium)
            assert output_fire == self.output_fire, \
                "CPU and Cavium code of element '%s' have different output firing types." % self.name
            self.code_cavium, self.output_code_cavium = (code, output_code)

    def analyze_output_type_internal(self, code):
        m = re.search('output[ ]*\{([^}]*)}', code)
        if m:
            # output { ... }
            output_fire = "all"
            program_code = code[:m.start(0)]
            out_code = ' ' + m.group(1)
            occurrence_out = self.count_ports_occurrence(out_code)

            for name, count in occurrence_out:
                if not count == 1:
                    raise Exception("Element '%s' must fire port '%s' exactly once, but it fires '%s' %d times."
                                    % (self.name, name, name, count))

            name2call = {}
            for port in self.outports:
                m = re.search('[^a-zA-Z0-9_](' + port.name + '[ ]*\([^;]*)', out_code)
                name2call[port.name] = m.group(1)

            output_code = name2call

        else:
            m = re.search('output[ ]+switch[ ]*\{([^}]*)}', code)
            if m:
                # output switch { ... }
                program_code = code[:m.start(0)]
                out_code = code[m.start(1):m.end(1)]
                cases = out_code.split(';')
                if re.search('^[ \n]*$', cases[-1]) is None:
                    raise Exception("Illegal form of output { ... } block in element '%s'." % self.name)
                count = {}
                cases = cases[:-1]

                m = re.search('^[ \n]*else[ ]*:[ ]*([a-zA-Z0-9_]+)(\([^)]*\))[ ]*$', cases[-1])
                if m:
                    # has else
                    output_fire = "one"
                    count[m.group(1)] = 1
                    cases = cases[:-1]
                    else_expr = m.group(1) + m.group(2)
                else:
                    # no else
                    output_fire = "zero_or_one"
                    else_expr = None

                cases_exprs = []
                for case in cases:
                    m = re.search('^[ \n]*case([^:]+):[ ]*([a-zA-Z0-9_]+)(\(.+)$', case)
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

                output_code = cases_exprs
            else:
                m = re.search('output[ ]+multiple[ ]*;', self.code)
                if m:
                    program_code = self.code[:m.start()]
                    output_fire = "multi"
                    output_code = {}
                    assert len(self.outports) == 1, \
                        ("Element '%s' must have only one output port because it may fire the output port more than once."
                         % self.name)
                else:
                    # no output area
                    if len(self.outports) > 0:
                        raise Exception("Element '%s' does not have output { ... } block." % self.name)
                    program_code = code
                    output_fire = "all"
                    output_code = {}

        # Check that it doesn't fire output port in program area.
        if not output_fire == "multi":
            occurrence_program = self.count_ports_occurrence(program_code)
            for name, count in occurrence_program:
                if count > 0:
                    raise Exception("Element '%s' fires port '%s' outside output { ... } block." % (self.name, name))

        return program_code, output_code, output_fire

    def get_output_code(self, order, device):
        if device == target.CAVIUM and self.output_code_cavium:
            return self.get_output_code_internal(self.output_code_cavium, order)
        return self.get_output_code_internal(self.output_code, order)

    def get_output_code_internal(self, output_code, order):
        src = ""
        if self.output_fire is None:
            if output_code:
                raise Exception("Element's output_fire is None, but its output_code is not None.")
            return src
        elif self.output_fire == "multi":
            return ""

        elif self.output_fire == "all":
            if len(order) == 0:
                for port in self.outports:
                    expr = output_code[port.name]
                    src += "  %s;\n" % expr
            elif len(order) == len(self.outports):
                for port_name in order:
                    expr = output_code[port_name]
                    src += "  %s;\n" % expr
            else:
                raise Exception("Element '%s' has %d output ports, but the order of ports only include %d ports."
                                % (self.name, len(self.outports), len(order)))
            return src

        else:
            cases_exprs = output_code
            if self.output_fire == "one":
                else_expr = cases_exprs[-1][1]
                cases_exprs = cases_exprs[:-1]
            else:
                else_expr = None

            src += self.generate_nested_if(cases_exprs, else_expr)
            return src

    def generate_nested_if(self, cases, else_expr):
        src = "  if(%s) { %s; }\n" % (cases[0][0], cases[0][1])
        for case_expr in cases[1:]:
            src += "  else if(%s) { %s; }\n" % (case_expr[0], case_expr[1])

        if else_expr:
            src += "  else { %s; }\n" % else_expr
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

    def get_code(self, device):
        if device == target.CAVIUM and self.code_cavium is not None:
            return self.code_cavium
        return self.code

    def prepend_code(self, add):
        self.code = add + self.code
        if self.code_cavium is not None:
            self.code_cavium = add + self.code_cavium

    def reassign_output_values_internal(self, portname, args, code, output_code):
        if self.output_fire == "all":
            output_code[portname] = "%s(%s)" % (portname, args)
        elif self.output_fire == "multi":
            m = re.search('[^a-zA-Z0-9_](' + portname + '[ ]*\([^;];)', code)
            while m:
                code = code[:m.start(1)] + "%s(%s);" % (portname, args) + code[m.end(1):]
                m = re.search('[^a-zA-Z0-9_](' + portname + '[ ]*\([^;];)', code)
        else:
            cases_exprs = output_code
            for i in range(len(cases_exprs)):
                expr = cases_exprs[i][1]
                m = re.match(portname + '[ ]*\(', expr)
                if m:
                    cases_exprs[i] = (cases_exprs[i][0], "%s(%s)" % (portname, args))
        return code, output_code

    def reassign_output_values(self, portname, args):
        (self.code, self.output_code) = \
            self.reassign_output_values_internal(portname, args, self.code, self.output_code)
        if self.code_cavium is not None:
            (self.code_cavium, self.output_code_cavium) = \
                self.reassign_output_values_internal(portname, args, self.code_cavium, self.output_code_cavium)

    def add_output_value_internal(self, portname, arg, code, output_code):
        if self.output_fire == "all":
            src = output_code[portname]
            src = src[:-1] + ", %s)" % arg
            output_code[portname] = src
        elif self.output_fire == "multi":
            m = re.search('[^a-zA-Z0-9_](' + portname + '[ ]*\([^;];)', code)
            while m:
                p = code.rfind(')', m.start(1), m.end(1))
                code = code[:p] + ", %s" % arg + code[p:]
                m = re.search('[^a-zA-Z0-9_](' + portname + '[ ]*\([^;];)', code)
        else:
            cases_exprs = output_code
            for i in range(len(cases_exprs)):
                expr = cases_exprs[i][1]
                m = re.match(portname + '[ ]*\(', expr)
                if m:
                    src = cases_exprs[i][1]
                    src = src[:-1] + ", %s)" % arg
                    cases_exprs[i] = (cases_exprs[i][0], src)
        return code, output_code

    def add_output_value(self, portname, arg):
        self.add_output_value_internal(portname, arg, self.code, self.output_code)

        if self.code_cavium is not None:
            self.add_output_value_internal(portname, arg, self.code_cavium, self.output_code_cavium)

    def replace_recursive(self, code, var, new_var):
        m = re.search(var, code)
        if m:
            code = code[:m.start(1)] + new_var + code[m.end(1):]
            return self.replace_recursive(code, var, new_var)
        else:
            return code

    def replace_in_code_internal(self, x, y, code, output_code):
        code = self.replace_recursive(code, x, y)

        if self.output_fire == "all":
            for port in output_code:
                work = output_code[port]
                work = self.replace_recursive(work, x, y)
                output_code[port] = work
        elif self.output_fire == "multi":
            pass
        else:
            for i in range(len(output_code)):
                case, work = output_code[i]
                work = self.replace_recursive(work, x, y)
                case = self.replace_recursive(case, x, y)
                output_code[i] = (case, work)

        return code, output_code

    def replace_in_code(self, x, y):
        (self.code, self.output_code) = self.replace_in_code_internal(x, y, self.code, self.output_code)
        if self.code_cavium is not None:
            (self.code_cavium, self.output_code_cavium) = \
                self.replace_in_code_internal(x, y, self.code_cavium, self.output_code_cavium)


class ElementNode:
    def __init__(self, name, element, state_args, thread="main"):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to (element name, port)
        self.input2ele = {}    # map input port name to list of (element name, port)
        self.output2connect = {}
        self.state_args = state_args
        self.core_id = False

        # Thread
        self.thread = thread
        self.process = None
        self.device = None

        # Join information
        self.join_ports_same_thread = None
        self.join_state_create = []  # which join buffers need to be created
        self.join_func_params = []   # which join buffers need to be passed as params
        self.join_output2save = {}   # which output ports need to be saved into join buffers
        self.join_call = []          # = 1 if this node needs to invoke the join element instance
        self.join_partial_order = []

        # API information
        self.API_return = None        # which state this node needs to return
        self.API_return_from = []   # which output node the the return value comes form
        self.API_return_final = None  # mark that this node has to create the return state
        self.API_default_val = None   # default return value

        # Liveness analysis
        self.liveness = None
        self.dominants = None
        self.passing_nodes = None
        self.dominant2kills = {}
        self.uses = None
        self.extras = set()
        self.special_fields = {}

    def deep_clone(self, suffix):
        new_element = self.element.clone(self.element.name + suffix)
        node = ElementNode(self.name + suffix, new_element, self.state_args)
        node.thread = self.thread
        node.process = self.process
        node.device = self.device
        node.liveness = self.liveness
        node.uses = self.uses
        node.extras = self.extras
        node.core_id = self.core_id
        return node

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
                        "The input port '%s' of element instance '%s' cannot be connected to multiple element instances %s\nbecause '%s' is a join element."
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

    def unused(self):
        if self.core_id:
            return False
        elif is_queue_clean(self):
            return False
        elif len(self.element.inports) > 0:
            return len(self.input2ele) == 0
        else:
            return len(self.element.outports) > 0 and len(self.output2ele) == 0

    def no_inport(self):
        return len(self.element.inports) == 0


class Port:
    def __init__(self, name, argtypes, pipeline=False):
        self.name = name
        self.argtypes = [common.sanitize_type(x) for x in argtypes]
        self.pipeline = pipeline

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.name == other.name and self.argtypes == other.argtypes

    def clone(self):
        return Port(self.name, self.argtypes[:], self.pipeline)


class State:
    def __init__(self, name, content, init=None, declare=True, fields=None, mapping=None):
        self.name = name
        self.content = content
        self.init = init
        self.processes = set()
        self.declare = declare
        self.mapping = mapping
        if fields:
            self.fields = fields
        elif content is not None:
            self.fields = self.extract_fields()
        else:
            self.fields = None

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.name == other.name and self.content == other.content and self.init == other.init)

    def extract_fields(self):
        fields = self.content.split(';')[:-1]  # ignore the last one
        return [common.get_var(f) for f in fields]


class StateNode:
    def __init__(self, name, state, init):
        self.name = name
        self.state = state
        self.init = init
        self.processes = set()
        self.buffer_for = None


class MemoryRegion:
    def __init__(self, name, size, init=None):
        self.name = name
        self.size = size
        self.init = init


class Queue:
    def __init__(self, name, size, n_cores, n_cases, enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                 enq_output=False):
        self.name = name
        self.size = size
        self.n_cores = n_cores
        self.n_cases = n_cases
        self.enq = None
        self.deq = None
        self.clean = None
        self.enq_blocking = enq_blocking
        self.deq_blocking = deq_blocking
        self.enq_atomic = enq_atomic
        self.deq_atomic = deq_atomic
        self.enq_output = enq_output

def is_queue_clean(instance):
    return instance.element.special == 'clean'