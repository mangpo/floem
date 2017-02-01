from graph import *


class ThreadAllocator:
    def __init__(self, graph, threads_api, threads_internal):
        self.threads_api = threads_api
        self.threads_internal = threads_internal
        self.threads_entry_point = threads_api.union(threads_internal)
        self.roots = set()
        self.joins = set()

        self.graph = graph
        self.instances = graph.instances

    """
    def external_api(self, name):
        self.threads_api.add(name)
        self.threads_entry_point.add(name)

    def internal_trigger(self, name):
        self.threads_internal.add(name)
        self.threads_entry_point.add(name)
        """

    def print_threads_info(self):
        print "Roots:", self.roots
        print "Entries:", self.threads_entry_point
        print "Joins:", self.joins

    def transform(self):
        self.assign_threads()
        #self.print_threads_info()
        self.insert_threading_elements()

    def find_roots(self):
        """
        :return: roots of the graph (elements that have no parent)
        """
        not_roots = set()
        for name in self.instances:
            instance = self.instances[name]
            for (next, port) in instance.output2ele.values():
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

    def assign_thread_dfs(self, instance, entry_points, name, last):
        """Traverse the graph in DFS fashion to assign threads.

        :param instance: current element instance
        :param entry_points: a set of thread entry elements
        :param name: current thread
        :param last: a map to decide where to marl "connect"
        :return:
        """
        if instance.thread is None:
            if len(instance.element.inports) > 1:
                self.joins.add(instance.name)
            if instance.name in entry_points:
                name = instance.name
            instance.thread = name
            for out in instance.output2ele:
                (next, port) = instance.output2ele[out]
                next = self.instances[next]
                self.assign_thread_dfs(next, entry_points, name, last)
                # Mark "save" because it connects to a join element.
                if len(next.element.inports) > 1:
                    instance.output2connect[out] = "save"
                    if next.thread == instance.thread:
                        last[next.name] = (instance,out)  # Potential port to mark "connect"
                # Mark "save" because it connects to an element with a different thread.
                if next.name in entry_points:
                    instance.output2connect[out] = "save"

    def insert_threading_elements(self):
        need_read = self.joins.union(self.threads_entry_point).difference(self.roots)
        for name in need_read:
            self.insert_buffer_read_element(self.instances[name])

        for instance in self.instances.values():
            self.insert_buffer_write_element(instance)

    def insert_buffer_read_element(self, instance):
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
        self.graph.addState(state)
        self.graph.newStateInstance(st_name, '_'+st_name)

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
        self.graph.addElement(ele)
        self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
        self.graph.connect(ele.name, instance.name, "out", None, True)

    def insert_buffer_write_element(self, instance):
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
            define = self.graph.addElement(ele)
            if define:
                self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
            self.graph.connect(instance.name, ele.name, out, None, True)

            if connect:
                self.graph.connect(ele_name, st_name+'_read')
