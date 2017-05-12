from graph import State


class InstancePart:
    """
    This class represents a subset of input ports of an element instance (part of instance).
    """
    def __init__(self, instance, ports, total):
        self.instance = instance
        self.ports = ports  # set
        self.total = total  # number of input ports

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.instance == other.instance and self.ports == other.ports

    def __str__(self):
        return self.instance + ":" + str(self.ports)

    def union(self, other):
        if self.instance == other.instance:
            ports = self.ports.union(other.ports)
            if len(ports) == self.total:
                return self.instance
            else:
                return InstancePart(self.instance, ports, self.total)
        else:
            return False

    def intersection(self, other):
        if self.instance == other.instance:
            ports = self.ports.intersection(other.ports)
            if len(ports) > 0:
                return InstancePart(self.instance, ports, self.total)
        return False


class FlowCollection:
    """
    This class represents a piece of data required to fire a join node.
    self.collection is a list of lists of InstancePart.
    A list of InstancePart represents a piece of data to the join node
    (an incomplete join nodes along a reversed path the join node -- we ignore complete join nodes).
    For example, [InstancePart(A, set(0), 2), InstancePart(B, set(1), 2)]
    represents a data from input port 1 of B to input port 0 of A.
    All instances in InstancePart are join nodes.
    FlowCollection with all data is a list of one entry [A].
    """

    def __init__(self, instance, total, port=None, is_port=True, goal=False):
        if port is None:
            self.collection = []
        else:
            if is_port:
                self.collection = [[InstancePart(instance, set([port]), total)]]
            else:
                self.collection = port
        self.target = instance
        self.total = total
        self.goal = goal  # True indicate if this FlowCollection ever reach the target instance whether complete or not

    def __str__(self):
        s = "["
        for x in self.collection:
            if isinstance(x, str):
                s += x
            else:
                s += "[" + ", ".join([str(p) for p in x]) + "]"
            s += ", "
        s += "]"
        return s

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.collection == other.collection and
                self.total == other.total and self.target == other.target)

    def clone(self):
        collection = []
        for l in self.collection:
            if isinstance(l, str):
                collection.append(l)
            else:
                collection.append(l[:])
        return FlowCollection(self.target, self.total, collection, False, self.goal)

    def add(self, y):
        """
        Add a piece of data.
        :param y: a piece of data, either a list of InstancePart, or a name of instance (all data)
        :return: void
        """
        if isinstance(y, str):
            # y is a name of instance, it represent all data. There can't be other data.
            if len(self.collection) == 0:
                self.collection.append(y)
                return
            else:
                raise Exception("The join instance '%s' is fired more than once in one run."
                                % self.target)

        new_flow = False
        for x in self.collection:
            if x == y:
                raise Exception("Port %s of the join instance '%s' is fired more than once in one run."
                                % (x, self.target))
            else:
                prefix_x = x[:-1]
                prefix_y = y[:-1]
                if prefix_x == prefix_y:
                    # When everything else is the same except the last InstancePart,
                    # try to merge them into a bigger piece of data.
                    intersect = x[-1].intersection(y[-1])
                    if intersect:
                        raise Exception("Port %s of the join instance '%s' is fired more than once in one run."
                                        % (x, self.target))
                    temp = x[-1].union(y[-1])
                    if temp:
                        if isinstance(temp, str):  # The last part is complete. Remove it from the list.
                            if len(prefix_x) == 0:
                                # If the prefix is empty, then the data is complete
                                # (which represents with the name of the join instance).
                                new_flow = self.target
                            else:
                                new_flow = prefix_x
                        else:
                            new_flow = prefix_x + [temp]
                        self.collection.remove(x)
                        break
        if new_flow:
            self.add(new_flow)
        else:
            self.collection.append(y)

    def union(self, other):
        """
        Union data collections
        :param other: FlowCollection
        :return: FlowCollection, the result of the union
        """
        new_o = self.clone()
        for x in other.collection:
            new_o.add(x)
        new_o.goal = self.goal or other.goal
        return new_o

    def intersection(self, other):
        """
        Intersect data collections
        :param other: FlowCollection
        :return: FlowCollection, the result of the intersection
        """
        collection = []
        for lx in self.collection:
            for ly in other.collection:
                if lx == ly:
                    collection.append(lx)
                elif lx[:-1] == ly[:-1]:
                    temp = lx[-1].intersection(ly[-1])
                    if temp:
                        collection.append(lx[:-1] + [temp])
        return FlowCollection(self.target, self.total, collection, is_port=False, goal=(self.goal or other.goal))

    def append(self, x):
        """
        Append InstancePart to the end of all pieces of data in the collection.
        :param x: InstancePart
        :return: void
        """
        for l in self.collection:
            l.append(x)

    def full(self):
        return self.collection == [self.target]

    def empty(self):
        return len(self.collection) == 0

    def happens_before(self, other):
        """
        Check if this FlowCollection should be ordered before the other one.
        :param other: other FlowCollection
        :return: True if it should be ordered before.
        """
        my_max_port = -1
        for l in self.collection:
            if isinstance(l[0], InstancePart):
                temp = max(l[0].ports)
                if temp > my_max_port:
                    my_max_port = temp

        other_max_port = -1
        for l in other.collection:
            if isinstance(l[0], InstancePart):
                temp = max(l[0].ports)
                if temp > other_max_port:
                    other_max_port = temp

        # self should be ordered before other, if the other contains the last call to the target.
        if (other_max_port == self.total - 1) and (my_max_port >= 0):
            return my_max_port < other_max_port

        # self should be ordered before other, if self is involved in calling the target but already complete,
        # and other is involved in calling the target but not yet complete.
        # see test_join_both_both_order in test_join_handling.py
        return (other_max_port >= 0) and self.goal and (my_max_port == -1)


def wrap_port(cover, instance, target, num_ports, port_name):
    """
    If instance is a join node, then return a part of the cover.
    :param cover: FlowCollection
    :param instance:
    :param target: target join node
    :param num_ports: number of input ports of the target join node
    :param port_name: an input port to instance
    :return: FlowCollection
    """
    if cover.full():
        return FlowCollection(target, num_ports, goal=True)
    else:
        if instance.join_ports_same_thread:  # Join node
            port_names = [port.name for port in instance.element.inports]
            index = port_names.index(port_name)
            temp = cover.clone()
            temp.append(InstancePart(instance.name, set([index]), len(instance.element.inports)))
            return temp
        else:
            return cover


def dfs_cover(g, node_name, port_name, target, num_ports, answer):
    """
    Traverse the graph 'g' and construction cover map 'answer'.
    :param g: graph of instance connection
    :param node_name: current node
    :param port_name: input port to the current node
    :param target: target join node
    :param num_ports: number of input ports of the target node
    :param answer: cover map, mapping node name to FlowCollection (its coverage of data required for the target node)
    :return: void
    """
    instance = g.instances[node_name]
    element = instance.element

    if node_name == target:
        port_names = [port.name for port in element.inports]
        index = port_names.index(port_name)
        return FlowCollection(target, num_ports, index, is_port=True, goal=True)  # Return one part of the full target.

    if node_name in answer:
        # Call wrap_port to return just a part of the full flow if this node is a join node.
        return wrap_port(answer[node_name], instance, target, num_ports, port_name)

    cover = FlowCollection(target, num_ports)  # Empty FlowCollection
    cover_map = {}
    for out_port in instance.output2ele:
        next_name, next_port = instance.output2ele[out_port]
        l_cover = dfs_cover(g, next_name, next_port, target, num_ports, answer)
        if element.output_fire == "all":
            intersect = cover.intersection(l_cover)
            if not intersect.empty():
                raise Exception("Element instance '%s' fires port %s of the join instance '%s' more than once."
                                % (node_name, intersect, target))
            cover_map[out_port] = l_cover
            cover = cover.union(l_cover)
        elif element.output_fire == "one":
            if len(cover_map) > 0 and not cover == l_cover:  # TODO: check
                raise Exception("When element instance '%s' fire only one port. All its output ports must fire the same input ports of the join instance '%s'."
                                % (node_name, target))
            cover_map[out_port] = l_cover
            cover = l_cover
        else:
            if not l_cover.full() and not l_cover.empty():
                raise Exception("When element instance '%s' fire zero or one port. Each of its output ports must fire none or all input ports of the join instance '%s'."
                    % (node_name, target))

    if element.output_fire == "all":
        # Use covers of all nodes to get partial orders.
        for out1 in cover_map:
            cover1 = cover_map[out1]
            for out2 in cover_map:
                cover2 = cover_map[out2]
                # out1 is called before out2 if cover2 includes a final call to the target node.
                if cover1.happens_before(cover2):
                    instance.join_partial_order.append((out1, out2))

    answer[node_name] = cover
    ret = wrap_port(cover, instance, target, num_ports, port_name)
    return ret


def annotate_for_instance(instance, g, roots, detail):
    """
    Mark each node an information about the given join element instance:
    1. if it needs to create the buffer state for the join node (instance.join_state_create)
    2. if it needs to receive the buffer point as a parameter (instance.join_func_params)
    3. if it needs to invoke the join node (instance.join_call)

    :param instance: join element instance (node)
    :param g: graph
    :param roots: roots of the graph
    :return: void
    """
    target = instance.name
    num_ports = len(instance.element.inports)
    answer = {}
    for root in roots:
        cover = dfs_cover(g, root, None, target, num_ports, answer)
        if not cover.empty():
            raise Exception("There is no dominant element instance for the join element instance '%s'." % instance.name)

    # Dominant nodes and passing nodes (all nodes between the dominant nodes and the target node)
    dominant_nodes = []
    passing_nodes = []
    for name in answer:
        cover = answer[name]
        if cover.full():
            dominant_nodes.append(name)
        elif not cover.empty():
            passing_nodes.append(name)

    if detail:
        # Mark this node to create a buffer for target join element.
        for dominant in dominant_nodes:
            g.instances[dominant].join_state_create.append(target)

        # Mark these nodes to pass pointer to the buffer.
        for node in passing_nodes:
            g.instances[node].join_func_params.append(target)

        # Mark this node to invoke the join element instance.
        last_port = instance.element.inports[-1]
        invoke_nodes = [name for name, port in instance.input2ele[last_port.name]]
        for node in invoke_nodes:
            g.instances[node].join_call.append(target)
    else:
        instance.dominants = dominant_nodes
        instance.passing_nodes = passing_nodes


def topo_sort(join_partial_order, order, visit, port_name):
    """
    Topologically sort nodes according to the partial orders. The output is saved in 'order'.
    :param join_partial_order: partial orders
    :param order: total order under construction
    :param visit: an array containing nodes that have already visitted
    :param port_name: current node
    :return: void
    """
    if port_name in order:
        return
    if port_name in visit:
        raise Exception("Cannot resolve order of function calls for all join elements due to a cycle in topological sort.")

    visit.append(port_name)
    for n1, n2 in join_partial_order:
        if port_name == n1:
            topo_sort(join_partial_order, order, visit, n2)
    order.append(port_name)


def order_function_calls(instance):
    """
    Order the output port calls of an element instance according to its partial port orders.
    :param instance:
    :return: void
    """
    if len(instance.join_partial_order) > 0:
        visit = []
        order = []
        iterate = instance.element.outports[:]
        iterate.reverse()  # Reverse because we want to preserve the original order if possible.
        for port in iterate:
            topo_sort(instance.join_partial_order, order, visit, port.name)
        order.reverse()
        instance.join_partial_order = order


def get_join_buffer_name(name):
    return "_%s_join_buffer" % name


def annotate_join_info(g, detail):
    """
    Annotate element instances in the given graph on information necessary to handle join nodes.
    :param g: graph
    :return: void
    """
    roots = g.find_roots()
    for instance in g.instances.values():
        nodes_same_thread = []
        ports_same_thread = []  # TODO: Why not all ports are in this list?
        save = {}
        # Count input ports on the same thread
        for port in instance.element.inports:
            if port.name in instance.input2ele:
                prev_name, prev_port = instance.input2ele[port.name][0]
                # Test only the first connection because all of them are on the same thread.
                if g.instances[prev_name].thread == instance.thread:
                    # Need to check this because when a join node has its own thread,
                    # its input ports connect to the same port of an introduced node,
                    # so it's no longer a join node.
                    if (prev_name, prev_port) not in nodes_same_thread:
                        nodes_same_thread.append((prev_name, prev_port))
                        ports_same_thread.append(port)
                for prev_name, prev_port in instance.input2ele[port.name]:
                    if prev_name in save:
                        save[prev_name].append(prev_port)
                    else:
                        save[prev_name] = [prev_port]
            else:
                ports_same_thread.append(port)

        # This is a join node.
        if len(ports_same_thread) > 1 and (instance.element.special is None):
            connect = 0
            for port in instance.element.inports:
                if port.name in instance.input2ele:
                    connect += 1

                # if port.name not in instance.input2ele:
                #     raise Exception("Input port '%s' of join element instance '%s' is not connected to any instance."
                #                     % (port.name, instance.name))

                # elif len(instance.input2ele[port.name]) > 1:
                #     raise Exception("Input port '%s' of join element instance '%s' is connected to more than one port."
                #                     % (port.name, instance.name))

            if connect > 0:
                assert connect == len(instance.element.inports), \
                    "Some input port of join element instance '%s' is not connected to any instance." % instance.name

                instance.join_ports_same_thread = ports_same_thread

                # Mark which output ports need to be saved into the join buffer.
                for node in save:
                    ports = save[node]
                    for port in ports:
                        g.instances[node].join_output2save[port] = instance.name

    for instance in g.instances.values():
        if instance.join_ports_same_thread:
            annotate_for_instance(instance, g, roots, detail)
            if detail:
                args = []
                content = ""
                for port in instance.join_ports_same_thread:
                    for i in range(len(port.argtypes)):
                        arg = "%s_arg%d" % (port.name, i)
                        args.append(arg)
                        content += "%s %s; " % (port.argtypes[i], arg)

                g.addState(State(get_join_buffer_name(instance.name), content, init=None))

    if detail:
        # Order function calls
        for instance in g.instances.values():
            order_function_calls(instance)


def clean_minimal_join_info(g):
    for instance in g.instances.values():
        instance.join_ports_same_thread = None