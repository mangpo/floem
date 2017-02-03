from graph import State

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


def dfs_dominant(g, name, target, answer):
    if name == target:
        return True, None
    if name in answer:
        return answer[name]

    instance = g.instances[name]
    ans = False
    my_last = [None]
    # Traverse the children based on the order of output ports, which is the order of calls inside the code.
    for port in instance.element.outports:
        if port.name in instance.output2ele:
            next_name, next_port = instance.output2ele[port.name]
            ret, last = dfs_dominant(g, next_name, target, answer)
            if ret is True:
                ans = name
                my_last[0] = name
            elif ret:
                if ans:
                    if not ret == ans:
                        ans = name
                        my_last[0] = last
                else:
                    ans = ret
                    my_last[0] = last
    answer[name] = ans, my_last[0]
    return ans, my_last[0]


def annotate_for_instance(instance, g, roots, save):
    target = instance.name
    answer = {}
    dominant, last_call = dfs_dominant(g, roots[0], target, answer)
    for root in roots[1:]:
        ret = dfs_dominant(g, root, target, answer)
        if not ret == dominant:
            raise Exception("There is no dominant element instance for the join element instance '%s'" % instance.name)

    passing_nodes = []
    for name in answer:
        if answer[name][0] and not answer[name][0] == dominant:
            passing_nodes.append(name)

    # Mark this node to create a buffer for target join element.
    g.instances[dominant].join_state_create.append(target)

    # Mark these nodes to pass pointer to the buffer.
    for node in passing_nodes:
        g.instances[node].join_func_params.append(target)

    # Mark this node to invoke the join element instance.
    g.instances[last_call].join_call.append(target)

    # Mark which output ports need to be saved into the join buffer.
    for node in save:
        ports = save[node]
        for port in ports:
            g.instances[node].join_output2save[port] = target

def get_join_buffer_name(name):
    return "_%s_join_buffer" % name

def annotate_join_info(g):
    roots = find_roots(g)
    for instance in g.instances.values():
        nodes_same_thread = []
        ports_same_thread = []
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

            instance.join_ports_same_thread = ports_same_thread
            annotate_for_instance(instance, g, roots, save)
            args = []
            content = ""
            for port in ports_same_thread:
                for i in range(len(port.argtypes)):
                    arg = "%s_arg%d" % (port.name, i)
                    args.append(arg)
                    content += "%s %s; " % (port.argtypes[i], arg)

            g.addState(State(get_join_buffer_name(instance.name), content, init=None))
