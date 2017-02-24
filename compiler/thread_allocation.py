from graph import *
import common


class ThreadAllocator:
    def __init__(self, graph, threads_api, threads_internal):
        self.threads_api = threads_api
        self.threads_internal = threads_internal
        self.threads_entry_point = threads_api.union(threads_internal)
        self.roots = set()
        self.joins = set()

        self.graph = graph
        self.instances = graph.instances

    def print_threads_info(self):
        print "Roots:", self.roots
        print "Entries:", self.threads_entry_point
        print "Joins:", self.joins

    def transform(self):
        # self.assign_threads()
        # self.check_APIs()
        # #self.print_threads_info()
        # self.insert_threading_elements()
        # return self.roots.difference(self.threads_api)

        self.find_roots()
        self.check_resources()
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
        self.graph.threads_roots = self.roots
        return self.roots

    def assign_threads(self):
        """
        Assign thread to each element. Each root and each element marked API or trigger has its own thread.
        For each remaining element, assign its thread to be the same as its first parent's thread.
        :return: void
        """
        roots = self.find_roots()
        last = {}
        for root in roots:
            self.assign_thread_dfs(self.instances[root], self.threads_entry_point, "main")


    def assign_thread_dfs(self, instance, entry_points, name):
        """Traverse the graph in DFS fashion to assign threads.

        :param instance: current element instance
        :param entry_points: a set of thread entry elements
        :param name: current thread
        :return: void
        """
        if instance.thread is None:
            if instance.name in entry_points:
                name = instance.name
            instance.thread = name
            for out in instance.output2ele:
                (next, port) = instance.output2ele[out]
                next = self.instances[next]
                self.assign_thread_dfs(next, entry_points, name)

    def dfs_collect_return(self, inst_name, thread, visit):
        instance = self.graph.instances[inst_name]
        if inst_name in visit:
            return ([], None, None)
        elif not instance.thread == thread:
            return ([], None, None)

        visit.add(inst_name)
        return_type = []
        return_inst = None
        return_port = None
        for port in instance.element.outports:
            if port.name in instance.output2ele:
                (next_inst, next_port) = instance.output2ele[port.name]
                ret = self.dfs_collect_return(next_inst, thread, visit)
                return_type += ret[0]
                if ret[1]:
                    return_inst = ret[1]
                if ret[2]:
                    return_port = ret[2]
            else:
                return_type += port.argtypes
                return_inst = inst_name
                return_port = port.name
        return return_type, return_inst, return_port

    def check_resources(self):
        thread2start = {}
        thread2instances = {}
        extra_edges = {}

        for instance in self.instances.values():
            t = instance.thread
            if t not in thread2instances:
                thread2instances[t] = []
            thread2instances[t].append(instance.name)

            if instance.thread_flag:
                if t in thread2start:
                    raise Exception("Resource '%s' has more than one starting element instance." % t)
                thread2start[t] = instance

        for api in self.graph.threads_API:
            assert (api.name in thread2start), ("API '%s' does not mark a starting element instance." % api.name)
            start = thread2start[api.name]
            api.call_instance = start.name

            if start.name in self.roots:
                # Receive input arguments.
                types = common.types_port_list(start.element.inports)
                assert types == api.call_types, \
                    ("API '%s' is defined to take arguments of types %s, but the starting element '%s' take arguments of types %s."
                     % (api.name, api.call_types, start.element.name, types))

            else:
                assert api.call_types == [], \
                    ("API '%s' should take no argument because the starting element instance '%s' receives arguments from other threads." \
                     % (api.name, start.name))

            visit = set()
            return_type, return_inst, return_port = self.dfs_collect_return(start.name, api.name, visit)
            if api.return_type:
                assert len(return_type) == 1 and return_type[0] == api.return_type, \
                    ("API '%s' should return '%s', but the returning element instance inside the API returns '%s'"
                     % (api.name, api.return_type, return_type))
            else:
                assert len(return_type) == 0, \
                    ("API '%s' should have no return value, but the returning element instance inside the API returns %s"
                     % (api.name, return_type))

            api.return_instance = return_inst
            api.return_port = return_port

        for trigger in self.graph.threads_internal2:
            assert (trigger.name in thread2start), \
                ("Internal trigger '%s' does not mark a starting element instance." % trigger.name)
            start = thread2start[trigger.name]
            trigger.call_instance = start.name

            if start.name in self.roots:
                assert len(start.element.inports) == 0, \
                    ("The starting element '%s' of internal trigger '%s' cannot take any argument."
                     % (start.name, trigger.name))

            visit = set()
            return_type, return_inst, return_port = self.dfs_collect_return(start.name, trigger.name, visit)
            assert return_type == [], ("Internal trigger '%s' should not return any value, but it returns %s"
                                       % (trigger.name, return_type))

    def check_APIs(self):
        """
        Check if the API functions are legal.
        """
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
                        "API '%s' -- call element instance '%s' should take no arguments, because inport port '%s' has already been connected."
                    % (api.name, api.call_instance, api.call_port))
            # else:
            elif api.call_instance in self.threads_internal:
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

            # Return type
            if api.state_name:
                argtypes = self.graph.get_outport_argtypes(api.return_instance, api.return_port)
                if len(argtypes) == 1 and (not argtypes[0] == api.state_name):
                    raise TypeError("API '%s' returns '%s', but '%s' is given as a return type." %
                                    (api.name, argtypes[0], api.state_name))

            # if api.state_name in common.primitive_types or self.graph.is_state(api.state_name):
            #     ports = [x for x in instance.element.outports if x.name in port_names]
            #     return_types = []
            #     for port in ports:
            #         return_types += port.argtypes
            #     if (not len(return_types) == 1) or (not return_types[0] == api.state_name):
            #         raise TypeError("API '%s' returns '%s', but '%s' is given as a return type." %
            #                         (api.name, ",".join(return_types), api.state_name))

    def insert_threading_elements(self):
        instances = self.instances.values();
        for instance in instances:
            self.insert_buffer_read_element(instance)
        for instance in instances:
            self.insert_buffer_write_element(instance)

    def insert_buffer_read_element(self, instance):
        need_buffer = []  # ports from different threads
        no_buffer = []    # ports from the same thread
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
            # Create read buffer element.
            new_name = self.create_buffer_read_element(instance, need_buffer, no_buffer)

            # Connect elements on the same thread to read buffer element.
            for port in no_buffer:
                for prev_name, prev_port in instance.input2ele[port.name]:
                    self.graph.connect(prev_name, new_name, prev_port, port.name, True)

            # Connect buffer element to current element instance.
            instance.input2ele = {}
            self.graph.connect(new_name, instance.name, "out", None)

            # Update thread entry points due to the new added node.
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

            for api in self.graph.threads_API:
                if api.call_instance == instance.name:
                    api.call_instance = new_name
            for trigger in self.graph.threads_internal2:
                if trigger.call_instance == instance.name:
                    trigger.call_instance = new_name

    def create_buffer_read_element(self, instance, need_buffer, no_buffer):
        clear = ""
        avails = []
        this_avails = []
        # Generate port available indicators.
        for port in need_buffer:
            avail = port.name + "_avail"
            this_avail = "this." + avail
            avails.append(avail)
            this_avails.append(this_avail)
            clear += "  %s = false;\n" % this_avail

        # Generate buffer variables.
        buffers_types, buffers = common.types_args_port_list(need_buffer, common.standard_arg_format)

        # State content
        st_content = ""
        st_init = [0 for i in range(len(avails) + len(buffers))]
        for avail in avails:
            st_content += "bool %s; " % avail
        for i in range(len(buffers)):
            st_content += "%s %s; " % (buffers_types[i], buffers[i])

        # Create state
        st_name = "_buffer_%s" % instance.name
        state = State(st_name, st_content, st_init)
        self.graph.addState(state)
        self.graph.newStateInstance(st_name, '_'+st_name)

        # All args
        all_types, all_args = common.types_args_port_list(instance.element.inports, common.standard_arg_format)

        # Read from input ports
        invoke = ""
        for port in no_buffer:
            types_args, args = common.types_args_one_port(port, common.standard_arg_format)
            invoke += "  (%s) = %s();\n" % (",".join(types_args), port.name)

        # Generate code to invoke the main element and clear available indicators.
        all_avails = " && ".join(this_avails)
        invoke += "  while(%s == false) { fflush(stdout); }\n" % all_avails
        for port in need_buffer:
            for i in range(len(port.argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                this_buffer = "this." + buffer
                invoke += "  %s %s = %s;\n" % (port.argtypes[i], buffer, this_buffer)
        invoke += clear
        invoke += "  output { out(%s); }\n" % ",".join(all_args)

        # Create element
        ele = Element(st_name+'_read', no_buffer, [Port("out", all_types)],
                      invoke, None, [(st_name, "this")])
        self.graph.addElement(ele)
        new_instance = self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
        new_instance.thread = instance.thread
        return ele.name

    def insert_buffer_write_element(self, instance):
        need_buffer = []  # ports to different threads
        no_buffer = []    # ports to the same thread
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
                # Create write buffer element.
                next_ele_name, next_port = instance.output2ele[port.name]
                new_name = self.create_buffer_write_element(instance, port, next_ele_name, next_port)
                self.graph.connect(instance.name, new_name, port.name, None, True)

    def create_buffer_write_element(self, instance, port, next_ele_name, next_port):
        avail = "this." + next_port + "_avail"

        # Runtime check.
        types_buffers = []
        buffers = []
        for i in range(len(port.argtypes)):
            buffer = common.standard_arg_format.format(next_port, i)
            buffers.append(buffer)
            types_buffers.append("%s %s" % (port.argtypes[i], buffer))

        src = "  (%s) = in();" % ",".join(types_buffers)
        src += "  while(%s == true) { fflush(stdout); }\n" % avail
        for i in range(len(port.argtypes)):
            buffer = buffers[i]
            src += "  this.%s = %s;\n" % (buffer, buffer)
        src += "  %s = 1;\n" % avail

        # Create element
        st_name = "_buffer_%s" % next_ele_name
        ele_name = st_name + '_' + next_port + "_write"
        ele = Element(ele_name, [Port("in", port.argtypes)], [], src, None, [(st_name, "this")])
        define = self.graph.addElement(ele)
        if define:
            new_instance = self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
            new_instance.thread = instance.thread
        return ele_name
