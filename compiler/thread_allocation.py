from graph import *
import common


class ThreadAllocator:
    def __init__(self, graph):
        self.roots = set()

        self.graph = graph
        self.instances = graph.instances

    def transform(self):
        """
        1. Impose control dependence order.
        2. Assign call_instance to each thread.
        3. Insert read/write buffer elements when necessary.
        """
        self.insert_resource_order()  # Impose scheduling order by inserting necessary edges.
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
        """
        1. Check that one thread has one starting element.
        2. Assign call_instance to a thread.
        """
        thread2start = {}
        thread2instances = {}

        # Check that one thread has one starting element.
        for instance in self.instances.values():
            t = instance.thread
            if t not in thread2instances:
                thread2instances[t] = []
            thread2instances[t].append(instance.name)

            if t and self.graph.is_start(instance):
                if t in thread2start:
                    raise Exception("Resource '%s' has more than one starting element instance." % t)
                thread2start[t] = instance

        # Assign call_instance to each API.
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

        # Assign call_instance to each internal trigger.
        for trigger in self.graph.threads_internal:
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
            for api in self.graph.threads_API:
                if api.call_instance == instance.name:
                    api.call_instance = new_name
            for trigger in self.graph.threads_internal:
                if trigger.call_instance == instance.name:
                    trigger.call_instance = new_name

    def create_buffer_read_element(self, instance, need_buffer, no_buffer):
        clear = ""
        avails = []
        this_avails = []
        # Generate port available indicators.
        for port in need_buffer:
            avail = port.name + "_avail"
            this_avail = "this->" + avail
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
        st_name = "%s_buffer" % instance.name
        state = State(st_name, st_content, st_init)
        self.graph.addState(state)
        self.graph.newStateInstance(st_name, '_'+st_name)
        state_inst = self.graph.state_instances['_'+st_name]
        state_inst.buffer_for = instance.name

        # All args
        all_types, all_args = common.types_args_port_list(instance.element.inports, common.standard_arg_format)

        # Read from input ports
        invoke = ""
        for port in no_buffer:
            types_args, args = common.types_args_one_port(port, common.standard_arg_format)
            invoke += "  (%s) = %s();\n" % (",".join(types_args), port.name)

        # Generate code to invoke the main element and clear available indicators.
        all_avails = " && ".join(this_avails)
        invoke += "  while(!(%s)) { __sync_synchronize(); }\n" % all_avails
        for port in need_buffer:
            for i in range(len(port.argtypes)):
                buffer = "%s_arg%d" % (port.name, i)
                this_buffer = "this->" + buffer
                invoke += "  %s %s = %s;\n" % (port.argtypes[i], buffer, this_buffer)
        invoke += clear
        invoke += "  __sync_synchronize();"
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
        avail = "this->" + next_port + "_avail"

        # Runtime check.
        types_buffers = []
        buffers = []
        for i in range(len(port.argtypes)):
            buffer = common.standard_arg_format.format(next_port, i)
            buffers.append(buffer)
            types_buffers.append("%s %s" % (port.argtypes[i], buffer))

        src = "  (%s) = in();" % ",".join(types_buffers)
        src += "  while(%s) { __sync_synchronize(); }\n" % avail
        for i in range(len(port.argtypes)):
            buffer = buffers[i]
            src += "  this->%s = %s;\n" % (buffer, buffer)
        src += "  %s = true;\n" % avail
        src += "  __sync_synchronize();"

        # Create element
        st_name = "%s_buffer" % next_ele_name
        ele_name = st_name + '_' + next_port + "_write"
        ele = Element(ele_name, [Port("in", port.argtypes)], [], src, None, [(st_name, "this")])
        define = self.graph.addElement(ele)
        if define:
            new_instance = self.graph.newElementInstance(ele.name, ele.name, ['_' + st_name])
            new_instance.thread = instance.thread
        return ele_name


    def insert_ports(self, inst_name, extra_in, extra_out):
        """
        Insert empty input and output ports to an instance, and insert connection accordingly.
        :param inst_name: instance
        :param extra_out: a list of (inst_name, port_id) that instance should connect to
        :param extra_in: a list of (inst_name, port_id) that instance should connect to
        :return:
        """
        instance = self.graph.instances[inst_name]
        suffix_in = ""
        suffix_out = ""
        if extra_in:
            suffix_in = "_i" + str(len(extra_in))
        if extra_out:
            suffix_out = "_o" + str(len(extra_out))

        # Create new element with extra ports.
        new_element = instance.element.clone(instance.element.name + "_clone" + suffix_in + suffix_out)
        if extra_out:
            new_element.add_empty_outports(["_out" + str(i) for i in range(len(extra_out))])
            for i in range(len(extra_out)):
                next_inst, id = extra_out[i]
                instance.output2ele["_out" + str(i)] = (next_inst, "_in" + str(id))

        if extra_in:
            new_element.add_empty_inports(["_in" + str(i) for i in range(len(extra_in))])
            for i in range(len(extra_in)):
                prev_inst, id = extra_in[i]
                instance.input2ele["_in" + str(i)] = [(prev_inst, "_out" + str(id))]

        self.graph.addElement(new_element)
        instance.element = new_element

    def insert_resource_order(self):
        """
        Insert input and output ports to impose the resource scheduling constraints.
        Insert connection accordingly.
        :return: void
        """
        bPointsTo = {}
        for a, b in self.graph.threads_order:
            if a not in bPointsTo:
                bPointsTo[a] = self.graph.find_subgraph(a, set())
            if b not in bPointsTo:
                bPointsTo[b] = self.graph.find_subgraph(b, set())

        # Collect extra input and output ports for every instance.
        extra_out = {}
        extra_in = {}
        for a, b in self.graph.threads_order:
            if a in bPointsTo[b]:  # b points to a, illegal
                raise Exception("Cannot order '{0}' before '{1}' because '{1}' points to '{0}'.".format(a, b))
            if b in bPointsTo[a]:
                continue  # if a already points to b, then we don't have to add this edge.

            if a not in extra_out:
                extra_out[a] = []
            if b not in extra_in:
                extra_in[b] = []
            len_a = len(extra_out[a])
            len_b = len(extra_in[b])
            extra_out[a].append((b, len_b))
            extra_in[b].append((a, len_a))

        # Insert ports.
        all_insts = set(extra_out.keys() + extra_in.keys())
        for inst in all_insts:
            my_extra_out = None
            my_extra_in = None
            if inst in extra_in:
                my_extra_in = extra_in[inst]
            if inst in extra_out:
                my_extra_out = extra_out[inst]
            self.insert_ports(inst, my_extra_in, my_extra_out)

