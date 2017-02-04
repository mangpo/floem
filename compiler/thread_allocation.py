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
        self.check_APIs()
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
        XXX 2. Mark "save" to an output port if it connects to a join element or an element with a different thread.
        XXX 3. Mark "connect" to an output port if it is the last port that connects a join element with the same threads.
        :return: void
        """
        roots = self.find_roots()
        last = {}
        for root in roots:
            self.assign_thread_dfs(self.instances[root], self.threads_entry_point, "main")

        # for (instance,out) in last.values():
        #     instance.output2connect[out] = "connect"

    def assign_thread_dfs(self, instance, entry_points, name):
        """Traverse the graph in DFS fashion to assign threads.

        :param instance: current element instance
        :param entry_points: a set of thread entry elements
        :param name: current thread
        :return:
        """
        if instance.thread is None:
            if instance.name in entry_points:
                name = instance.name
            instance.thread = name
            for out in instance.output2ele:
                (next, port) = instance.output2ele[out]
                next = self.instances[next]
                self.assign_thread_dfs(next, entry_points, name)

    def check_APIs(self):
        for api in self.graph.APIs:
            # Call and return are at the same thread.
            if not self.instances[api.call_instance].thread == self.instances[api.return_instance].thread:
                raise Exception("API '%s' -- call element instance '%s' must be on the same thread as return element instance '%s'."
                                % (api.name, api.call_instance, api.return_instance))

            # Arguments
            if api.call_instance in self.roots:
                instance = self.instances[api.call_instance]
                port_names = [x.name for x in instance.element.inports]
                if len(port_names) > 1:
                    raise TypeError(
                        "API '%s' -- call element instance '%s' must have zero or one input port."
                        % (api.name, api.call_instance))
                elif len(port_names) == 1:
                    if not api.call_port == port_names[0]:
                        raise TypeError(
                            "API '%s' -- call element instance '%s' takes port '%s' as arguments. The given argument port is '%s'."
                            % (api.name, api.call_instance, port_names, api.call_port))
                elif api.call_port:
                    raise TypeError(
                        "API '%s' -- call element instance '%s' takes no arguments, but argument port '%s' is given."
                    % (api.name, api.call_instance, api.call_port))

            elif api.call_instance in self.threads_api:
                if not api.call_port == None:
                    raise TypeError(
                        "API '%s' -- call element instance '%s' takes no arguments. The given argument port is '%s'."
                    % (api.name, api.call_instance, api.call_port))
            else:
                raise TypeError(
                    "API '%s' -- call element instance '%s' is not marked as external trigger."
                    % (api.name, api.call_instance))

            # Return
            instance = self.instances[api.return_instance]
            port_names = [x.name for x in instance.element.outports]
            for port in instance.output2ele:
                (next_ele, next_port) = instance.output2ele[port]
                if next_ele not in self.threads_entry_point:
                    raise TypeError(
                        "API '%s' -- return element instance '%s' has a continuing element instance '%s' on the same thread. This is illegal."
                        % (api.name, api.return_instance, next_ele))
                port_names.remove(port)

            if len(port_names) > 1:
                raise TypeError(
                    "API '%s' -- return element instance '%s' must have zero or one unwired output port."
                    % (api.name, api.return_instance))
            elif len(port_names) == 1:
                if not api.return_port == port_names[0]:
                    raise TypeError(
                        "API '%s' -- return element instance '%s' have port '%s' as return values. The given return port is '%s'."
                        % (api.name, api.return_instance, port_names[0], api.return_port))
            elif api.return_port:
                raise TypeError(
                    "API '%s' -- return element instance '%s' has no return value, but return port '%s' is given."
                    % (api.name, api.return_instance, api.return_port))

    def insert_threading_elements(self):
        instances = self.instances.values();
        for instance in instances:
            self.insert_buffer_read_element(instance)
        for instance in instances:
            self.insert_buffer_write_element(instance)

        # need_read = self.joins.union(self.threads_entry_point).difference(self.roots)
        # for name in need_read:
        #     self.insert_buffer_read_element(self.instances[name])
        #
        # for instance in self.instances.values():
        #     self.insert_buffer_write_element(instance)
        #     self.insert_buffer_return_element(instance)

    def insert_buffer_read_element(self, instance):
        need_buffer = []
        no_buffer = []
        for port in instance.element.inports:
            if port.name in instance.input2ele:
                port_list = instance.input2ele[port.name]
                name_list = [prev_name for (prev_name, prev_port) in port_list]
                thread_list = [self.instances[prev_name].thread for prev_name in name_list]
                if len(set(thread_list)) > 1:
                    raise Exception("Port '%s' of element instance '%s' is connected to multiple instances %s that run on different threads."
                                    % (port.name, instance.name, name_list))
                if thread_list[0] == instance.thread:
                    no_buffer.append(port)
                else:
                    need_buffer.append(port)
            else:
                # This input port is not connected to anything yet.
                no_buffer.append(port)

        if len(need_buffer) > 0:
            # Create read buffer element
            new_name = self.create_buffer_read_element(instance, need_buffer, no_buffer)
            new_instance = self.instances[new_name]

            # Connect elements on the same thread to read buffer element
            for port in no_buffer:
                for prev_name, prev_port in instance.input2ele[port.name]:
                    self.graph.connect(prev_name, new_name, prev_port, port.name, True)

            # Connect buffer element to current element instance
            instance.input2ele = {}
            self.graph.connect(new_name, instance.name, "out", None)

            if instance.name in self.threads_api:
                self.threads_api.remove(instance.name)
                self.threads_entry_point.remove(instance.name)
                self.threads_api.add(new_name)
                self.threads_entry_point.add(new_name)
            elif instance.name in self.threads_internal:
                self.threads_internal.remove(instance.name)
                self.threads_entry_point.remove(instance.name)
                self.threads_internal.add(new_name)
                self.threads_entry_point.add(new_name)
            for api in self.graph.APIs:
                if api.call_instance == instance.name:
                    api.call_instance = new_name

    def create_buffer_read_element(self, instance, need_buffer, no_buffer):
        inports = instance.element.inports
        clear = ""
        avails = []
        this_avails = []
        # Generate port available indicators.
        for port in need_buffer:
            avail = port.name + "_avail"
            this_avail = "this." + avail
            avails.append(avail)
            this_avails.append(this_avail)
            clear += "  %s = 0;\n" % this_avail

        # Generate buffer variables.
        buffers = []
        buffers_types = []
        for port in need_buffer:
            argtypes = port.argtypes
            for i in range(len(argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                buffers.append(buffer)
                buffers_types.append(argtypes[i])

        # State content
        st_content = ""
        st_init = ",".join(["0" for i in range(len(avails) + len(buffers))])
        for avail in avails:
            st_content += "int %s; " % avail
        for i in range(len(buffers)):
            st_content += "%s %s; " % (buffers_types[i], buffers[i])

        # Create state
        st_name = "_buffer_%s" % instance.name
        state = State(st_name, st_content, st_init)
        self.graph.addState(state)
        self.graph.newStateInstance(st_name, '_'+st_name)

        # All args
        all_types = []
        all_args = []
        for port in instance.element.inports:
            for i in range(len(port.argtypes)):
                all_args.append("%s_arg%d" % (port.name, i))
                all_types.append(port.argtypes[i])

        # Read from input ports
                invoke = ""
        for port in no_buffer:
            args = []
            types_args = []
            for i in range(len(port.argtypes)):
                arg = "%s_arg%d" % (port.name, i)
                args.append(arg)
                types_args.append("%s %s" % (port.argtypes[i], arg))
            invoke += "  (%s) = %s();\n" % (",".join(types_args), port.name)

        # Generate code to invoke the main element and clear available indicators.
        all_avails = " && ".join(this_avails)
        invoke += "  while(!(%s));\n" % all_avails
        for port in need_buffer:
            for i in range(len(port.argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                this_buffer = "this." + buffer
                invoke += "  %s %s = %s;\n" % (port.argtypes[i], buffer, this_buffer)
        invoke += clear
        invoke += "  out(%s);\n" % ",".join(all_args)

        # Create element
        ele = Element(st_name+'_read', no_buffer, [Port("out", all_types)],
                      invoke, None, [(st_name, "this")])
        self.graph.addElement(ele)
        new_instance = self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
        new_instance.thread = instance.thread
        return ele.name

    def insert_buffer_write_element(self, instance):
        need_buffer = []
        no_buffer = []
        for port in instance.element.outports:
            if port.name in instance.output2ele:
                next_name, next_port = instance.output2ele[port.name]
                if self.instances[next_name].thread == instance.thread:
                    no_buffer.append(port)
                else:
                    need_buffer.append(port)
            else:
                # This output port is not connected to anything yet.
                no_buffer.append(port)

        if len(need_buffer) > 0:
            for port in need_buffer:
                next_ele_name, next_port = instance.output2ele[port.name]
                new_name = self.create_buffer_write_element(instance, port, next_ele_name, next_port)
                self.graph.connect(instance.name, new_name, port.name, None, True)

    def create_buffer_write_element(self, instance, port, next_ele_name, next_port):
        avail = "this." + next_port + "_avail"

        # Runtime check.
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

        # Output port
        out_port = []

        # Create element
        st_name = "_buffer_%s" % next_ele_name
        ele_name = st_name + '_' + next_port + "_write"
        ele = Element(ele_name, [Port("in", port.argtypes)], out_port,
                      src, None, [(st_name, "this")])
        define = self.graph.addElement(ele)
        if define:
            new_instance = self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
            new_instance.thread = instance.thread
        return ele_name

    # def insert_buffer_return_element(self, instance):
    #     for api in self.APIs:
    #         if api.return_instance == instance.name:
    #
    #             if api.name in self.APIcode:
    #                 raise Exception("API '%s' has more than one instantiation. This is illegal." % api.name)
    #
    #             st_name = None
    #             st_instance_name = None
    #             if api.return_port:
    #                 st_name = api.state_name
    #                 st_instance_name = '_' + st_name + '_' + instance.name
    #
    #             # Create element to store return values
    #             if api.return_port:
    #                 instance = self.instances[api.return_instance]
    #                 outport = [port for port in instance.element.outports if port.name == api.return_port][0]
    #
    #                 # Generate buffer variables.
    #                 buffers = []
    #                 argtypes = outport.argtypes
    #                 types_buffers = []
    #                 for i in range(len(argtypes)):
    #                     buffer = "arg%d" % i
    #                     buffers.append(buffer)
    #                     types_buffers.append("%s %s" % (argtypes[i], buffer))
    #
    #                 # State content
    #                 avail = "avail"
    #                 st_content = ""
    #                 st_init = "0," + ",".join(["0" for i in range(len(buffers))])
    #                 st_content += "int %s; " % avail
    #                 for i in range(len(buffers)):
    #                     st_content += "%s %s; " % (argtypes[i], buffers[i])
    #
    #                 # Create state
    #                 state = State(st_name, st_content, st_init)
    #                 self.graph.addState(state)
    #                 self.graph.newStateInstance(st_name, st_instance_name)
    #
    #                 # Runtime check.
    #                 src = "  (%s) = in();" % ",".join(types_buffers)
    #                 # Only check if it's the first port.
    #                 src += "  if(this.%s == 1) { printf(\"Join failed (overwriting some values).\\n\"); exit(-1); }\n" \
    #                        % avail
    #                 for i in range(len(argtypes)):
    #                     src += "  this.%s = %s;\n" % (buffers[i], buffers[i])
    #                 src += "  this.%s = 1;\n" % avail
    #
    #                 # Create element
    #                 ele_name = st_instance_name + "_write"
    #                 ele = Element(ele_name, [Port("in", argtypes)], [],
    #                               src, None, [(st_name, "this")])
    #                 self.graph.addElement(ele)
    #                 self.graph.newElementInstance(ele.name, ele.name, [st_instance_name])
    #                 self.graph.connect(instance.name, ele.name, outport.name, None, True)
    #
    #
    #             # Create API function
    #             args = []
    #             types_args = []
    #             call_instance = self.instances[api.call_instance]
    #
    #             if api.call_port:
    #                 inport = [port for port in instance.element.inports if port.name == api.call_port][0]
    #                 for i in range(len(inport.argtypes)):
    #                     arg = "arg%d" % i
    #                     args.append(arg)
    #                     types_args.append("%s %s" % (inport.argtypes[i], arg))
    #
    #             src = ""
    #             if api.return_port is None:
    #                 src += "void"
    #             else:
    #                 src += "struct " + api.state_name
    #             src += " %s(%s) {\n" % (api.name, ",".join(types_args))
    #             src += "  %s(%s);\n" % (api.call_instance, ",".join(args))
    #             if api.return_port:
    #                 # TODO: optimization
    #                 src += "  struct %s temp = %s;\n" % (api.state_name, st_instance_name)
    #                 src += "  %s.avail = 0;\n" % st_instance_name
    #                 src += "  return temp;\n"
    #             src += "}\n"
    #             self.APIcode[api.name] = src
