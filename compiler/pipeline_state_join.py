from graph import *


def add_release_port(g, instance):
    new_element = instance.element.clone(instance.name + "_merge_version")
    new_element.outports.append(Port("release", []))
    new_element.output_code["release"] = "release()"
    g.addElement(new_element)
    instance.element = new_element


def add_release_entry_port(g, instance):
    new_element = instance.element.clone(instance.name + "_release_version")
    new_element.outports.append(Port("release", ["q_entry*"]))
    new_element.output_code["release"] = "release(state.entry)"
    g.addElement(new_element)
    instance.element = new_element


def merge_as_join(g, nodes, name):
    n = len(nodes)
    join = Element("merge%d" % n,
                         [Port("in" + str(i), []) for i in range(n)],
                         [],
                         r'''output { }''')
    new_inst_name = name + "_merge%d" % n
    g.addElement(join)
    g.newElementInstance(new_inst_name, join.name, [])

    i = 0
    for instance in nodes:
        add_release_port(g, instance)
        g.connect(instance.name, new_inst_name, "release", "in" + str(i))
        i += 1

    return g.instances[new_inst_name]


def merge_as_no_join(g, nodes, name):
    n = len(nodes)
    join = Element("merge",
                   [Port("in", [])],
                   [],
                   r'''output { }''')
    new_inst_name = name + "_merge"
    g.addElement(join)
    g.newElementInstance(new_inst_name, join.name, [])

    for instance in nodes:
        add_release_port(g, instance)
        g.connect(instance.name, new_inst_name)

    return g.instances[new_inst_name]


def handle_either_or_node(instance, g, lives, ans):
    merge_nodes = []
    for next_name, next_port in instance.output2ele:
        ret = live_leaf_nodes(next_name, g, lives, ans)
        if len(ret) == 0:
            merge_nodes.append(g.instances[next_name])
        elif len(ret) == 1:
            merge_nodes += [x for x in ret]
        else:
            merge_nodes.append(merge_as_join(g, ret, next_name))

    return merge_as_no_join(g, merge_nodes, instance.name)


def live_leaf_nodes(name, g, lives, ans):
    if name in ans:
        return ans[name]

    instance = g.instances[name]
    element = instance.element
    if len(lives.intersection(instance.uses)) == 0:
        ret = set()
    elif element.output_fire == "all":
        ret = set()
        for next_name, next_port in instance.output2ele:
            ret = ret.union(live_leaf_nodes(next_name, g, lives, ans))
        if len(ret) == 0:
            ret = set([instance])
    elif element.output_fire == "one":
        ret = set([handle_either_or_node(instance, g, lives, ans)])
    else:
        raise Exception("Cannot insert dequeue release automatically due to Element '%s', which may not fire any port."
                        % instance.element)

    ans[name] = ret
    return ret


def get_node_before_release(name, g, lives):
    ans = {}
    ret = live_leaf_nodes(name, g, lives, ans)
    if len(ret) == 0:
        node = g.instances[name]
    elif len(ret) == 1:
        node = [x for x in ret][0]
    else:
        node = merge_as_join(g, ret, name)

    add_release_entry_port(g, node)
    return node