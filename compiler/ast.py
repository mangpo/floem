class Element:

    def __init__(self, name, inports, outports, code, local_state=None, state_params=[]):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = code
        self.local_state = local_state
        self.state_params = state_params


class ElementInstance:
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
        return self.element + "::" + self.name

    def print_details(self):
        print "Element {"
        print "  type:", self.element.name, "| name:", self.name
        print "  thread:", self.thread
        print "  out-port:", self.output2ele
        print "  mark:", self.output2connect
        print "}"


class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes


class State:
    def __init__(self, name, content, init=None):
        self.name = name
        self.content = content
        self.init = init


class Graph:
    def __init__(self, elements, states=[]):
        self.elements = {}
        self.instances = {}
        self.states = {}
        self.state_instances = {}
        for e in elements:
            self.elements[e.name] = e
        for s in states:
            self.states[s.name] = s

        #: TODO: move to a different class
        self.threads_entry_point = set()
        self.threads_api = set()
        self.threads_internal = set()
        self.roots = set()
        self.joins = set()

    def addState(self,state):
        self.states[state.name] = state

    def addElement(self,element):
        self.elements[element.name] = element

    def newStateInstance(self, state, name):
        s = self.states[state]
        self.state_instances[name] = s

    def defineInstance(self, element, name, state_args=[]):
        e = self.elements[element]
        self.instances[name] = ElementInstance(name, e, state_args)

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
            #assert (len(e2.inports) == 1)
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

    def external_api(self, name):
        self.threads_api.add(name)
        self.threads_entry_point.add(name)

    def internal_trigger(self, name):
        self.threads_internal.add(name)
        self.threads_entry_point.add(name)

    def print_threads_info(self):
        print "Roots:", self.roots
        print "Entries:", self.threads_entry_point
        print "Joins:", self.joins
        for instance in self.instances.values():
            instance.print_details()

    def find_roots(self):
        """
        :return: roots of the graph (elements that have no parent)
        """
        not_roots = set()
        for name in self.instances:
            instance = self.instances[name]
            for (next,port) in instance.output2ele.values():
                not_roots.add(next)

        self.roots = set(self.instances.keys()).difference(not_roots)
        return self.roots

    def assign_threads(self):
        """
        1. Assign thread to each element. Each root and each element marked API or trigger has its own thread.
        For each remaining element, assign its thread to be the same as its first parent's thread.
        2. Mark "save" to an output port if it connects to a join element or an element with a different thread.
        3. Mark "connect" to an output port if it is the last port that connects a join element with the same threads.
        :return: void
        """
        roots = self.find_roots()
        entry_points = roots.union(self.threads_entry_point)
        last = {}
        for root in roots:
            self.assign_thread_dfs(self.instances[root], entry_points, root, last)

        for (instance,out) in last.values():
            instance.output2connect[out] = "connect"

    def assign_thread_dfs(self, instance, roots, name, last):
        """Traverse the graph in DFS fashion to assign threads.

        :param instance: current element instance
        :param roots: a set of thread entry elements
        :param name: current thread
        :param last: a map to decide where to marl "connect"
        :return:
        """
        if instance.thread is None:
            if len(instance.element.inports) > 1:
                self.joins.add(instance.name)
            if instance.name in roots:
                name = instance.name
            instance.thread = name
            for out in instance.output2ele:
                (next,port) = instance.output2ele[out]
                next = self.instances[next]
                self.assign_thread_dfs(next, roots, name, last)
                # Mark "save" because it connects to a join element.
                if len(next.element.inports) > 1:
                    instance.output2connect[out] = "save"
                    if next.thread == instance.thread:
                        last[next.name] = (instance,out)  # Potential port to mark "connect"
                # Mark "save" because it connects to an element with a different thread.
                if not(next.thread == instance.thread):
                    instance.output2connect[out] = "save"

    def insert_theading_elements(self):
        need_read = self.joins.union(self.threads_entry_point).difference(self.roots)
        for name in need_read:
            self.buffer_read_element(self.instances[name])

        for instance in self.instances.values():
            self.buffer_write_element(instance)

    def buffer_read_element(self, instance):
        clear = ""
        avails = []
        this_avails = []
        inports = instance.element.inports
        # Generate port available indicators.
        for port in instance.element.inports:
            avail = port.name + "_avail"
            this_avail = "this." + avail
            avails.append(avail)
            this_avails.append(this_avail)
            clear += "  %s = 0;\n" % this_avail

        # Generate buffer variables.
        buffers = []
        buffers_types = []
        for port in inports:
            argtypes = port.argtypes
            for i in range(len(argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                buffers.append(buffer)
                buffers_types.append(argtypes[i])

        # State content
        st_content = ""
        st_init = ",".join(["0" for i in range(len(avails) + len(buffers))])
        for avail in avails:
            st_content += "int %s; " % avail;
        for i in range(len(buffers)):
            st_content += "%s %s; " % (buffers_types[i], buffers[i])

        # Create state
        st_name = "_buffer_%s" % instance.name
        state = State(st_name, st_content, st_init)
        self.addState(state)
        self.newStateInstance(st_name, '_'+st_name)

        # Generate code to invoke the main element and clear available indicators.
        all_avails = " && ".join(this_avails)
        invoke = "  in();\n"
        invoke += "  while(!(%s));\n" % all_avails
        for port in inports:
            for i in range(len(port.argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                this_buffer = "this." + buffer
                invoke += "  %s %s = %s;\n" % (port.argtypes[i], buffer, this_buffer)
        invoke += clear
        invoke += "  out(%s);\n" % ",".join(buffers)

        # Create element
        ele = Element(st_name+'_read', [Port("in", [])], [Port("out", buffers_types)],
                      invoke, None, [(st_name, "this")])
        self.addElement(ele)
        self.defineInstance(ele.name, ele.name, ['_'+st_name])
        self.connect(ele.name, instance.name, "out")

    def buffer_write_element(self, instance):
        for out in instance.output2connect:
            action = instance.output2connect[out]
            next_ele_name, next_port = instance.output2ele[out]
            avail = "this." + next_port + "_avail"
            port = [port for port in instance.element.outports if port.name == out][0]

            # Runtime check.
            connect = (instance.output2connect[out] == "connect")
            types_buffers = []
            buffers = []
            for i in range(len(port.argtypes)):
                buffer = "%s_arg%d" % (next_port, i)
                buffers.append(buffer)
                types_buffers.append("%s %s" % (port.argtypes[i], buffer))

            src = "  (%s) = in();" % ",".join(types_buffers)
            src += "  if(%s == 1) { printf(\"Join failed (overwriting some values).\\n\"); exit(-1); }\n" \
                   % avail
            for i in range(len(port.argtypes)):
                buffer = buffers[i]
                src += "  this.%s = %s;\n" % (buffer, buffer)
            src += "  %s = 1;\n" % avail
            if connect:
                src += "  out();"

            # Output port
            out_port = []
            if connect:
                out_port.append(Port("out", []))

            # Create element
            st_name = "_buffer_%s" % next_ele_name
            ele_name = st_name + '_' + next_port + "_write"
            ele = Element(ele_name, [Port("in", port.argtypes)], out_port,
                          src, None, [(st_name, "this")])
            self.addElement(ele)
            self.defineInstance(ele.name, ele.name, ['_'+st_name])
            self.connect(instance.name, ele.name, out)

            if connect:
                self.connect(ele.name, st_name+'_read')