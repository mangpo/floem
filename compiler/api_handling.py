from graph import State
import common
from join_handling import FlowCollection, InstancePart


def mark_return(g, api, cover_map, target, node_name, visit):
    """
    Given a cover_map, determine which nodes need to return a return value.
    1. what return state it should return (instance.API_return)
    2. which nodes it receives the return state from (instance.API_return_from which is a list)
    3. does it need to construct the return state (instance.API_return_final)

    :param g: graph
    :param api: APIFunction
    :param cover_map: cover map constructed by dfs_cover_return function
    :param target: return node
    :param node_name: current node
    :return: always_return
    """
    if node_name in visit:
        return visit[node_name]

    instance = g.instances[node_name]
    instance.API_return = api.return_type
    instance.API_default_val = api.default_val

    if target == node_name:
        instance.API_return_final = api
        if instance.element.output_fire == "zero_or_one":
            visit[node_name] = False
            return False
        else:
            visit[node_name] = True
            return True

    # Collect potential children nodes that the current node gets a return value from.
    return_nodes = []
    for out_port in instance.output2ele:
        next_name, next_port = instance.output2ele[out_port]
        cover = cover_map[next_name]
        if not cover.empty():
            return_nodes.append(next_name)
    l = len(return_nodes)

    if instance.element.output_fire == "all":
        if l == 0:
            raise Exception("API '%s' never returns a return value." % api.name)
        elif l == 1:
            instance.API_return_from = [return_nodes[0]]
            my_return = mark_return(g, api, cover_map, target, return_nodes[0], visit)
        else:
            # When multiple children nodes invoke the return node, the one that is executed last has the return value.
            last = instance.join_partial_order[-1]
            next_name, next_port = instance.output2ele[last]
            instance.API_return_from = [next_name]
            my_return = mark_return(g, api, cover_map, target, next_name, visit)
    else:
        # When the current node has switch output,
        # all of the collect children nodes, whose outputs flow to the return node, may have the return value.
        instance.API_return_from = return_nodes
        always_return = True
        for next_name in return_nodes:
            ret = mark_return(g, api, cover_map, target, next_name, visit)
            always_return = always_return and ret
        if instance.element.output_fire == "one":
            my_return = always_return
        else:
            my_return = False

    visit[node_name] = my_return
    return my_return


def wrap_port(cover, instance, port_name):
    """
    If instance is a join node, then return a part of the cover.
    :param cover: FlowCollection
    :param instance:
    :param port_name: an input port to instance
    :return: FlowCollection
    """
    if instance.join_ports_same_thread:  # Join node
        if isinstance(port_name, str):
            port_names = [port.name for port in instance.element.inports]
            index = port_names.index(port_name)
            temp = cover.clone()
            temp.append(InstancePart(instance.name, set([index]), len(instance.element.inports)))
            return temp
        else:
            # Handle the inserted read node due to resource allocation before a join node.
            assert (len(port_name) == len(instance.element.inports))
            return cover

    else:
        return cover


def dfs_cover_return(g, node_name, port_name, target, num_ports, answer):
    """
        Traverse the graph 'g' and construction cover map 'answer'.
        :param g: graph of instance connection
        :param node_name: current node
        :param port_name: input port to the current node
        :param target: return node
        :param num_ports: number of input ports of the target node
        :param answer: cover map, mapping node name to FlowCollection (its coverage of data required for the target node)
        :return: void
    """
    instance = g.instances[node_name]
    element = instance.element

    if node_name == target:
        if num_ports > 1:
            if isinstance(port_name, str):
                port_names = [port.name for port in element.inports]
                index = port_names.index(port_name)
                cover = FlowCollection(target, num_ports, index, is_port=True, goal=True)  # Return one part of the full target.
            else:
                # Handle the inserted read node due to resource allocation before a join node.
                assert (len(port_name) == num_ports)
                cover = FlowCollection(target, num_ports, port=[target], is_port=False,
                                       goal=True)  # Return the full target.
        else:
            cover = FlowCollection(target, num_ports, port=[target], is_port=False, goal=True)  # Return the full target.
        answer[node_name] = cover
        return cover

    if node_name in answer:
        # Call wrap_port to return just a part of the full flow if this node is a join node.
        return wrap_port(answer[node_name], instance, port_name)

    cover = FlowCollection(target, num_ports)  # Empty FlowCollection
    for out_port in instance.output2ele:
        next_name, next_port = instance.output2ele[out_port]
        l_cover = dfs_cover_return(g, next_name, next_port, target, num_ports, answer)

        if element.output_fire == "all":
            intersect = cover.intersection(l_cover)
            if not intersect.empty():
                raise Exception("Element instance '%s' fires port %s of the return instance '%s' more than once."
                                % (node_name, intersect, target))
            cover = cover.union(l_cover)
        elif element.output_fire == "one":
            # Not as strict as join handling
            cover_empty = cover.empty()
            if not cover_empty and not l_cover.empty() and not cover == l_cover:
                raise Exception(
                    "When element instance '%s' fire only one port. All its output ports must fire the same input ports of the return instance '%s'."
                    % (node_name, target))
            if cover_empty:
                cover = l_cover
        else:
            if not l_cover.full() and not l_cover.empty():
                raise Exception(
                    "When element instance '%s' fire zero or one port. Each of its output ports must fire none or all input ports of the return instance '%s'."
                    % (node_name, target))
            if cover.empty():
                cover = l_cover  # Upperbound scenario. Assume a port with a return value is fired.

    answer[node_name] = cover
    return wrap_port(cover, instance, port_name)


def annotate_api_info(g):
    """
    Annotate element instances in the given graph on information necessary to create API functions.
    :param g: computation graph
    :return: void
    """
    for api in g.threads_API:
        if api.return_type:
            # Check that this API is legal.
            cover_map = {}
            return_instance = g.instances[api.return_instance]
            num_ports = len(return_instance.element.inports)
            cover = dfs_cover_return(g, api.call_instance, None, api.return_instance, num_ports, cover_map)

            if cover.empty():
                raise Exception("API '%s' is incomplete. It never returns a return value." % api.name)  # TODO: test
            elif not cover.full():
                raise Exception("API '%s' is incomplete. It returns a return value more than once." % api.name)  # TODO: test

            always_return = mark_return(g, api, cover_map, api.return_instance, api.call_instance, {})
            if (not always_return) and (not api.default_val):
                raise Exception("API '%s' doesn't always return, and the default return value is not provided." %
                                api.name)
