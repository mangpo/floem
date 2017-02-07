from graph import State

class InstancePart:
    def __init__(self, instance, ports, total):
        self.instance = instance
        self.ports = ports  # set
        self.total = total

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

    def __init__(self, instance, total, port=None, is_port=True):
        if port is None:
            self.collection = []
        else:
            if is_port:
                self.collection = [[InstancePart(instance, set([port]), total)]]
            else:
                self.collection = port
        self.target = instance
        self.total = total

    def __str__(self):
        s = "["
        for x in self.collection:
            if isinstance(x, str):
                s += x
            else:
                print x
                s += "[" + ", ".join([str(p) for p in x]) + "]"
            s += ", "
        s += "]"
        return s


    def clone(self):
        collection = []
        for l in self.collection:
            if isinstance(l, str):
                collection.append(l)
            else:
                collection.append(l[:])
        return FlowCollection(self.target, self.total, collection, False)

    def add(self, y):
        if isinstance(y, str):
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
                    intersect = x[-1].intersection(y[-1])
                    if intersect:
                        raise Exception("Port %s of the join instance '%s' is fired more than once in one run."
                                        % (x, self.target))
                    temp = x[-1].union(y[-1])
                    if temp:
                        if isinstance(temp, str):
                            if len(prefix_x) == 0:
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
        new_o = self.clone()
        for x in other.collection:
            new_o.add(x)
        return new_o

    def intersection(self, other):
        collection = []
        for lx in self.collection:
            for ly in other.collection:
                if lx == ly:
                    collection.append(lx)
                elif lx[:-1] == ly[:-1]:
                    temp = lx[-1].intersection(ly[-1])
                    if temp:
                        collection.append(lx[:-1] + [temp])
        return FlowCollection(self.target, self.total, collection, is_port=False)

    def append(self, x):
        for l in self.collection:
            l.append(x)

    def full(self):
        return self.collection == [self.target]

    def empty(self):
        return len(self.collection) == 0

    def happens_before(self, other):
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

        return (other_max_port == self.total - 1) and (my_max_port >= 0) and (my_max_port < other_max_port)


def find_roots(g):
    """
    :return: roots of the graph (elements that have no parent)
    """
    not_roots = set()
    for name in g.instances:
        instance = g.instances[name]
        for (next, port) in instance.output2ele.values():
            not_roots.add(next)

    roots = set(g.instances.keys()).difference(not_roots)
    return [x for x in roots]


# def dfs_dominant(g, name, target, answer):
#     """
#     Find a dominant node D of the target node T in the graph.
#     D dominates T if all nodes in the graph that can reach T has to pass D.
#
#     :param g: graph
#     :param name: current node
#     :param target: target node
#     :param answer: a map of (node, local D). This function constructs this map.
#     For each node V, it stores a dominant node with respect to the local view of V.
#     :return: (D, last_call)
#     D         -- the dominant node
#     last_call -- the last node that immediately reach D, last in term of the order of execution in the code.
#     """
#     if name == target:
#         return True, None
#     if name in answer:
#         return answer[name]
#
#     instance = g.instances[name]
#     ans = False
#     my_last = [None]
#     # Traverse the children based on the order of output ports, which is the order of calls inside the code.
#     for port in instance.element.outports:
#         if port.name in instance.output2ele:
#             next_name, next_port = instance.output2ele[port.name]
#             ret, last = dfs_dominant(g, next_name, target, answer)
#             if ret is True:
#                 ans = name
#                 my_last[0] = name
#             elif ret:
#                 if ans:
#                     if not ret == ans:
#                         # If the return nodes from its children are no the same,
#                         # then the node itself is a dominant node.
#                         ans = name
#                         my_last[0] = last
#                 else:
#                     # When there is no current dominant node,
#                     # a dominant node returned from a child can be a dominant node.
#                     ans = ret
#                     my_last[0] = last
#     answer[name] = ans, my_last[0]
#     return ans, my_last[0]
#

def wrap_port(cover, instance, target, num_ports, port_name):
    if cover.full():
        return FlowCollection(target, num_ports)
    else:
        if instance.join_ports_same_thread:
            port_names = [port.name for port in instance.element.inports]
            index = port_names.index(port_name)
            temp = cover.clone()
            temp.append(InstancePart(instance.name, set([index]), len(instance.element.inports)))
            return temp
        else:
            return cover


def dfs_cover(g, node_name, port_name, target, num_ports, answer):
    instance = g.instances[node_name]
    element = instance.element

    if node_name == target:
        port_names = [port.name for port in element.inports]
        index = port_names.index(port_name)
        return FlowCollection(target, num_ports, index) #set([i])
        # raise Exception("Element '%s' doesn't have input port '%s'." % (ele_name, port_name))

    if node_name in answer:
        return wrap_port(answer[node_name], instance, target, num_ports, port_name)

    cover = FlowCollection(target, num_ports)
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
            cover_empty = cover.empty()
            if not cover_empty and not l_cover.empty() > 0 and not cover == l_cover:
                raise Exception("When element instance '%s' fire only one port. All its output ports must fire the same input ports of the join instance '%s'."
                                % (node_name, target))
            if cover_empty:
                cover = l_cover
        else:
            if len(l_cover) > 0:
                raise Exception("When element instance '%s' fire zero or one port. Each of its output ports must fire none or all input ports of the join instance '%s'."
                    % (node_name, target))

    if element.output_fire == "all":
        for out1 in cover_map:
            cover1 = cover_map[out1]
            for out2 in cover_map:
                cover2 = cover_map[out2]
                if cover1.happens_before(cover2):
                    instance.join_partial_order.append((out1, out2))

    answer[node_name] = cover
    return wrap_port(cover, instance, target, num_ports, port_name)


def annotate_for_instance(instance, g, roots, save):
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

    # Mark which output ports need to be saved into the join buffer.
    # for node in save:
    #     ports = save[node]
    #     for port in ports:
    #         g.instances[node].join_output2save[port] = target


def topo_sort(join_partial_order, order, visit, port_name):
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
    if len(instance.join_partial_order) > 0:
        visit = []
        order = []
        iterate = instance.element.outports[:]
        iterate.reverse()
        for port in iterate:
            topo_sort(instance.join_partial_order, order, visit, port.name)
        order.reverse()
        instance.join_partial_order = order

#
# def annotate_for_instance(instance, g, roots, save):
#     """
#     Mark each node an information about the given join element instance:
#     1. if it needs to create the buffer state for the join node (instance.join_state_create)
#     2. if it needs to receive the buffer point as a parameter (instance.join_func_params)
#     3. if it needs to save any port data to the buffer state (instance.join_output2save)
#     4. if it needs to invoke the join node (instance.join_call)
#
#     :param instance: join element instance (node)
#     :param g: graph
#     :param roots: roots of the graph
#     :param save: a map of (node, ports) where node needs to save ports' content to the buffer state
#     :return: void
#     """
#     target = instance.name
#     answer = {}
#     dominant, last_call = dfs_dominant(g, roots[0], target, answer)
#     for root in roots[1:]:
#         ret = dfs_dominant(g, root, target, answer)
#         if not ret == dominant:
#             raise Exception("There is no dominant element instance for the join element instance '%s'" % instance.name)
#
#     # Find all nodes between the dominant node and the target node.
#     passing_nodes = []
#     for name in answer:
#         if answer[name][0] and not answer[name][0] == dominant:
#             passing_nodes.append(name)
#
#     # Mark this node to create a buffer for target join element.
#     g.instances[dominant].join_state_create.append(target)
#
#     # Mark these nodes to pass pointer to the buffer.
#     for node in passing_nodes:
#         g.instances[node].join_func_params.append(target)
#
#     # Mark this node to invoke the join element instance.
#     g.instances[last_call].join_call.append(target)
#
#     # Mark which output ports need to be saved into the join buffer.
#     for node in save:
#         ports = save[node]
#         for port in ports:
#             g.instances[node].join_output2save[port] = target


def get_join_buffer_name(name):
    return "_%s_join_buffer" % name


def annotate_join_info(g):
    """
    Annotate element instances in the given graph on information necessary to handle join nodes.
    :param g: graph
    :return: void
    """
    roots = find_roots(g)
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
        if len(ports_same_thread) > 1:
            for port in instance.element.inports:
                if port.name not in instance.input2ele:
                    raise Exception("Input port '%s' of join element instance '%s' is not connected to any instance."
                                    % (port.name, instance.name))
                elif len(instance.input2ele[port.name]) > 1:
                    raise Exception("Input port '%s' of join element instance '%s' is connected to more than one port."
                                    % (port.name, instance.name))

            instance.join_ports_same_thread = ports_same_thread

            # Mark which output ports need to be saved into the join buffer.
            for node in save:
                ports = save[node]
                for port in ports:
                    g.instances[node].join_output2save[port] = instance.name

    for instance in g.instances.values():
        if instance.join_ports_same_thread:
            annotate_for_instance(instance, g, roots, save)
            args = []
            content = ""
            for port in ports_same_thread:
                for i in range(len(port.argtypes)):
                    arg = "%s_arg%d" % (port.name, i)
                    args.append(arg)
                    content += "%s %s; " % (port.argtypes[i], arg)

            g.addState(State(get_join_buffer_name(instance.name), content, init=None))

    # Order function calls
    for instance in g.instances.values():
        order_function_calls(instance)