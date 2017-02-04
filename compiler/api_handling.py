from graph import State
import ctypes

def dfs_find_path(g, name, target_name, path):
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
    instance = g.instances[name]
    if instance.API_return:
        raise Exception("Element instance '%s' can only compose one API. However, it is parts of APIs that return '%s' and '%s'."
                        % (name, instance.API_return, api.state_name))
    else:
        instance.API_return = api.state_name

    next = path[name]
    if next is True:
        instance.API_return_final = api
    else:
        instance.API_return_from = next
        mark_return(g, next, path, api)

def annotate_api_info(g):
    for api in g.APIs:
        if api.state_name:
            path = {}
            dfs_find_path(g, api.call_instance, api.return_instance, path)
            mark_return(g, api.call_instance, path, api)

            content = " "
            for port in g.instances[api.return_instance].element.outports:
                if port.name == api.return_port:
                    for i in range(len(port.argtypes)):
                        type_arg = "%s %s_arg%d; " % (port.argtypes[i], port.name, i)
                        content += type_arg
            if api.state_name not in ctypes.primitive_types and not g.is_state(api.state_name):
                api.new_state_type = True
                g.addState(State(api.state_name, content, init=None))