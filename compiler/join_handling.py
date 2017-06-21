from graph import State
from thread_allocation import ThreadAllocator
from process_handling import annotate_process_info
from api_handling import *

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
                raise Exception("When element instance '%s' fires only one port. All its output ports must fire the same input ports of the join instance '%s'."
                                % (node_name, target))
            cover_map[out_port] = l_cover
            cover = l_cover
        elif element.output_fire == "multi":
            if not l_cover.empty():
                raise Exception("When element instance '%s' may fire its output port multiple times.\n" %node_name +
                                "Its output port must trigger all ports of the join instance '%s'." % target)
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


def check_pipeline_state_liveness(g):
    for instance in g.instances.values():
        if len(instance.input2ele) == 0 and instance.liveness:
            assert len(instance.liveness) == 0, \
                ("Fields %s of a pipeline state should not be live at the beginning at element instance '%s'." %
                 (instance.liveness, instance.name))


def clean_minimal_join_info(g):
    for instance in g.instances.values():
        instance.join_ports_same_thread = None


def join_and_resource_annotation_pass(graph, resource, remove_unused):
    if resource:
        # Insert necessary elements for resource mapping.
        # Assign call_instance for each thread.
        # Check that one thread has one starting element.
        # Impose control dependence order.
        t = ThreadAllocator(graph)
        t.transform()
    else:
        graph.clear_APIs()

    if remove_unused:
        graph.remove_unused_elements(resource)

    # Annotate detailed join information
    annotate_join_info(graph, True)

    if resource:
        # Annotate APIs information. APIs ony make sense with resource mapping.
        annotate_api_info(graph)

    annotate_process_info(graph)

    if remove_unused:
        graph.remove_unused_states()

    check_pipeline_state_liveness(graph)