from graph import *


def add_release_port(g, instance):
    new_element = instance.element.clone(instance.name + "_merge_version")
    new_element.outports.append(Port("release", []))
    new_element.reassign_output_values("release", '')
    g.addElement(new_element)
    instance.element = new_element


def add_release_entry_port(g, instance):
    new_element = instance.element.clone(instance.element.name + "_release_version")
    new_element.outports.append(Port("release", ["q_buffer"]))
    new_element.reassign_output_values("release", "state.buffer")
    g.addElement(new_element)
    instance.element = new_element


def merge_as_join(g, nodes, name, prefix, lives):
    n = len(nodes)
    threads = set([inst.thread for inst in nodes])
    if len(set(threads)) > 1:
        raise Exception(
            "Cannot create a merge node to release queue entries for elements that run on different threads: %s"
            % nodes)

    join = Element("merge%d" % n, [Port("in" + str(i), []) for i in range(n)], [], r'''output { }''')
    new_inst_name = name + "_merge%d" % n
    g.addElement(join)
    g.newElementInstance(join.name, prefix + new_inst_name, [])
    instance = g.instances[prefix + new_inst_name]
    instance.liveness = set()
    instance.uses = lives
    instance.extras = set()

    i = 0
    for instance in nodes:
        add_release_port(g, instance)
        g.connect(instance.name, new_inst_name, "release", "in" + str(i))
        i += 1

    node = g.instances[new_inst_name]
    node.thread = [t for t in threads][0]

    return node


def merge_as_no_join(g, nodes, name, prefix, lives):
    threads = set([inst.thread for inst in nodes])
    if len(set(threads)) > 1:
        raise Exception(
            "Cannot create a merge node to release queue entries for elements that run on different threads: %s"
            % nodes)

    join = Element("merge", [Port("in", [])], [], r'''output { }''')
    new_inst_name = name + "_merge"
    g.addElement(join)
    g.newElementInstance(join.name, prefix + new_inst_name, [])
    instance = g.instances[prefix + new_inst_name]
    instance.liveness = set()
    instance.uses = lives
    instance.extras = set()

    for instance in nodes:
        add_release_port(g, instance)
        g.connect(instance.name, new_inst_name, 'release')

    node = g.instances[new_inst_name]
    node.thread = [t for t in threads][0]

    return node


def handle_either_or_node(instance, g, lives, ans, prefix):
    merge_nodes = []
    for next_name, next_port in instance.output2ele.values():
        ret = live_leaf_nodes(next_name, g, lives, ans, prefix)
        if len(ret) == 0:
            inst = g.instances[next_name]
            inst.uses = lives
            merge_nodes.append(inst)
        elif len(ret) == 1:
            merge_nodes += [x for x in ret]
        else:
            merge_nodes.append(merge_as_join(g, ret, next_name, prefix))

    return merge_as_no_join(g, merge_nodes, instance.name, prefix, lives)


def live_leaf_nodes(name, g, lives, ans, prefix):
    if name in ans:
        return ans[name]

    instance = g.instances[name]
    element = instance.element
    if instance.uses is None or len(lives.intersection(instance.uses)) == 0:
        ret = set()
    elif element.output_fire == "all":
        ret = set()
        for next_name, next_port in instance.output2ele.values():
            ret = ret.union(live_leaf_nodes(next_name, g, lives, ans, prefix))
        if len(ret) == 0:
            ret = set([instance])
    elif element.output_fire == "one":
        ret = set([handle_either_or_node(instance, g, lives, ans, prefix)])
    else:
        raise Exception("Cannot insert dequeue release automatically due to Element '%s', which may not fire any port."
                        % instance.element)

    ans[name] = ret
    return ret


def get_node_before_release(name, g, lives, prefix, vis):
    """
    :param name: root instance
    :param g: graph
    :param lives: live variables at root
    :param prefix:
    :return: node that will connect to deq_release node
    """
    ans = {}
    ret = live_leaf_nodes(name, g, lives, ans, prefix)
    if len(ret) == 0:
        node = g.instances[name]
    elif len(ret) == 1:
        node = [x for x in ret][0]
    else:
        node = merge_as_join(g, ret, name, prefix, lives)

    if node not in vis:
        add_release_entry_port(g, node)
    return node