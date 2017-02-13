from graph import State
import common


def dfs_find_path(g, name, target_name, path):
    """
    Construct a map that will be sued to construct a path to the target node.

    :param g: graph
    :param name: current node
    :param target_name: target node
    :param path: A map that stores an edge to the next node in the API path.
                 This map will be used to construct a path to the target node.
                 This function is creating this map.
    :return: the next node in the path from this node to target.
    """
    if name in path:
        return path[name]

    if name == target_name:
        path[name] = True
        return True

    instance = g.instances[name]
    my_ans = [False]
    for port in instance.element.outports:
        if port.name in instance.output2ele:
            next_name, next_port = instance.output2ele[port.name]
            ret = dfs_find_path(g, next_name, target_name, path)
            if ret:
                # Save the last connection to the return node.
                my_ans[0] = next_name
    path[name] = my_ans[0]
    return my_ans[0]


def mark_return(g, name, path, api):
    """
    Given a path, mark each node along with path:
    1. what return state it should return (instance.API_return)
    2. which node it receives the return state from (instance.API_return_from)
    3. does it need to construct the return state (instance.API_return_final)

    :param g: graph
    :param name: current node
    :param path: a map that stores an edge to the next node in the API path.
    :param api: APIFunction
    :return: void
    """
    instance = g.instances[name]
    if instance.API_return:
        if not instance.API_return == api.state_name:
            raise Exception(
                r'''Element instance '%s' can only compose APIs that return the same state.
                However, it is parts of APIs that return '%s' and '%s'.'''
                % (name, instance.API_return, api.state_name))

        next = path[name]
        if next is True:
            if not instance.API_return_final.return_port == api.return_port:
                raise Exception(
                    r'''Element instance '%s' can only compose APIs that return the same state from the same port.
                    However, it is parts of APIs that return from ports '%s' and '%s'.'''
                    % (name, instance.API_return_final.return_port, api.return_portinstance.API_return))
        else:
            if not instance.API_return_from == next:
                raise Exception(
                    r'''Element instance '%s' can only compose APIs that return the same state from the same port.
                    However, it is parts of APIs that return from element instances '%s' and '%s'.'''
                    % (name, instance.API_return_from, next))
            mark_return(g, next, path, api)

    else:
        instance.API_return = api.state_name
        next = path[name]
        if next is True:
            instance.API_return_final = api
        else:
            instance.API_return_from = next
            mark_return(g, next, path, api)


def annotate_api_info(g):
    """
    Annotate element instances in the given graph on information necessary to create API functions.
    :param g: computation graph
    :return: void
    """
    for api in g.APIs:
        if api.state_name:
            # Find a path from call node to return node. This path is used for passing the return value.
            path = {}
            dfs_find_path(g, api.call_instance, api.return_instance, path)
            mark_return(g, api.call_instance, path, api)

            # Create return state.
            content = " "
            for port in g.instances[api.return_instance].element.outports:
                if port.name == api.return_port:
                    for i in range(len(port.argtypes)):
                        type_arg = "%s %s_arg%d; " % (port.argtypes[i], port.name, i)
                        content += type_arg
            if api.state_name not in common.primitive_types and not g.is_state(api.state_name):
                api.new_state_type = True
                g.addState(State(api.state_name, content, init=None))
