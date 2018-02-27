import graph_ir, cache, workspace, desugaring
import pipeline_state_join
from program import *


def dfs_same_thread(g, s, t, vis, prev=None, queues=[]):
    if s.name in vis:
        return vis[s.name]
    if s == t:
        return queues

    vis[s.name] = False
    q = s.element.special
    if isinstance(q, graph_ir.Queue):
        queues.append(q)

        id = None
        for port_name in q.enq.input2ele:
            prev_name, prev_port = q.enq.input2ele[port_name]
            if prev_name == prev:
                id = int(port_name[3:])
                break

        next_name, next_port = q.deq.output2ele['out' + str(id)]
        ans = dfs_same_thread(g, g.instances[next_name], t, vis, s.name, queues)

    else:
        ans = False
        for inst_name, port in s.output2ele.values():
            next = g.instances[inst_name]
            ret = dfs_same_thread(g, next, t, vis, s.name, queues)
            if ans is False:
                ans = ret
            else:
                assert ret == ans, \
                    "All output ports of CacheStart must reach CacheEnd, or all reach the same queue. %s does not meet this property." \
                    % s.name

    assert ans is not False, "Some outputs of %s do not reach %s or queue." % (s.name, t.name)
    vis[s.name] = ans
    return ans


def transform_get(g, s, t, CacheGet, CacheSetGet, CacheRelease):
    # 1. Check that get_start and get_end is on the same device.
    if s.thread in g.thread2process:
        p1 = g.thread2process[s.thread]
    else:
        p1 = 'main'
    if t.thread in g.thread2process:
        p2 = g.thread2process[t.thread]
    else:
        p2 = 'main'
    assert p1 == p2, "%s and %s must be running the same device." % (s.name, t.name)

    # 2. Duplicate everything after t if s and t are on different threads (queue in between)
    API_return = None
    if s.thread != t.thread:
        subgraph = g.find_subgraph_list(t.name, [])
        dup_nodes = reversed(subgraph[:-1])
        if dup_nodes[-1] in g.API_outputs:
            API_return = dup_nodes[-1]
        pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_cache', copy=2)

        hit_start = dup_nodes[0] + '_cache1'  # hit
        subgraph = g.find_subgraph_list(hit_start, [])
        for name in subgraph:
            g.instances[name].thread = s.thread

        rel_after = [dup_nodes[0] + '_cache0', dup_nodes[0] + '_cache1']
    else:
        hit_start = t.output2ele['out'][0]
        rel_after = [hit_start]

    # 3. Insert cache_rel
    if CacheRelease:
        cache_rel_inst = CacheRelease(create=False).instance
        rel_element = cache_rel_inst.element
        rel_element = rel_element.clone(rel_element.name + "_for_get")
        g.addElement(rel_element)
        cache_rel_inst.element = rel_element

        if API_return:
            # Adjust release element
            API_instance = g.instances[API_return]
            types = API_instance.element.outports[0].argtypes
            args = ['ret{0}'.format(i) for i in range(len(types))]
            rel_element.inports = [Port('inp', types, rel_element.inports[0].pipeline)]
            rel_element.outports = [Port('out', types, rel_element.outports[0].pipeline)]
            rel_element.reassign_input_values('inp', types, args)
            rel_element.reassign_output_values('out', args)

            # Connect release element
            g.newElementInstance(cache_rel_inst.element, cache_rel_inst.name, cache_rel_inst.args)
            g.set_thread(cache_rel_inst.name, s.therad)

            g.connect(API_return, cache_rel_inst.name, API_instance.element.outports[0].name)
            index = g.API_outputs.index(API_return)
            g.API_outputs[index] = cache_rel_inst.name
        else:
            # Adjust release element
            rel_element.remove_outport('out')

            # Connect release element
            for i in range(len(rel_after)):
                g.newElementInstance(cache_rel_inst.element, cache_rel_inst.name + str(i), cache_rel_inst.args)
                g.set_thread(cache_rel_inst.name+ str(i), node.therad)
                node = pipeline_state_join.get_node_before_release_nolive(rel_after, g, '', {})
                g.connect(node.name, cache_rel_inst.name, 'release')

    # 4. Insert cache_get
    cache_get_inst = CacheGet(create=False).instance
    g.newElementInstance(cache_get_inst.element, cache_get_inst.name, cache_get_inst.args)
    g.set_thread(cache_get_inst.name, s.thread)

    # replace dummy get_start with real get
    if len(s.input2ele) > 0:
        inport = 'inp'
        l = s.input2ele[inport]
        while len(l) > 0:
            prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
            g.disconnect(prev_name, s.name, prev_port, inport)
            g.connect(prev_name, cache_get_inst.name, prev_port, 'inp')

    outport = 'out'
    next_name, next_port = s.output2ele[outport]
    g.disconnect(s.name, next_name, outport, next_port)
    g.connect(cache_get_inst.name, next_name, 'miss', next_port)
    g.connect(cache_get_inst.name, hit_start, 'hit', 'inp')

    g.deleteElementInstance(s.name)

    # 5. Insert cache_set
    cache_set_inst = CacheSetGet(create=False).instance
    g.newElementInstance(cache_set_inst.element, cache_set_inst.name, cache_set_inst.args)
    g.set_thread(cache_set_inst.name, s.thread)

    # replace dummy get_end with real set
    inport = 'inp'
    l = t.input2ele[inport]
    while len(l) > 0:
        prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
        g.disconnect(prev_name, t.name, prev_port, inport)
        g.connect(prev_name, cache_set_inst.name, prev_port, 'inp')

    outport = 'out'
    next_name, next_port = t.output2ele[outport]
    g.disconnect(t.name, next_name, outport, next_port)
    g.connect(cache_set_inst.name, next_name, 'out', next_port)

    g.deleteElementInstance(t.name)


def transform_set(g, set_start, set_end, CacheGet, CacheSet, CacheRelease, write_policy, write_miss):
    pass


def create_cache(cache_high):
    workspace.push_decl()
    workspace.push_scope(cache_high.name)
    CacheGet, CacheSet, CacheSetGet, CacheUpdate, CacheRelease = \
        cache.cache_default(cache_high.name, cache_high.key_type, cache_high.val_type,
                            var_size=cache_high.var_size, hash_value=cache_high.hash_value,
                            update_func=cache_high.update_func, release_type=[],
                            write_policy=cache_high.write_policy, write_miss=cache_high.write_miss)

    CacheGet(create=False)
    CacheSet(create=False)
    CacheSetGet(create=False)
    CacheUpdate(create=False)
    if CacheRelease:
        CacheRelease(create=False)

    decl = workspace.pop_decl()
    scope, collection = workspace.pop_scope()
    p = Program(*(decl + scope))
    dp = desugaring.desugar(p)
    g = program_to_graph_pass(dp, default_process='tmp')

    return g, CacheGet, CacheSet, CacheSetGet, CacheUpdate, CacheRelease


def cache_pass(g):
    caches = []
    for instance in g.instances.values():
        c = instance.element.special
        if isinstance(c, graph_ir.Cache):
            if c not in caches:
                caches.append(c)

    for cache_high in caches:
        g_add, CacheGet, CacheSet, CacheSetGet, CacheUpdate, CacheRelease = create_cache(cache_high)
        g.merge(g_add)

        get_reach = None
        set_reach = None
        if cache_high.get_start:
            get_start = g.instances[cache_high.get_start.name]
            get_end = g.instances[cache_high.get_end.name]
            get_reach = dfs_same_thread(g, get_start, get_end, {})

            transform_get(g, get_start, get_end, CacheGet, CacheSetGet, CacheRelease)

        if cache_high.set_start:
            set_start = g.instances[cache_high.set_start.name]
            set_end = g.instances[cache_high.set_end.name]
            set_reach = dfs_same_thread(g, set_start, set_end, {})

            transform_set(g, set_start, set_end, CacheGet, CacheSet, CacheRelease,
                          cache_high.write_policy, cache_high.write_miss)

        if get_reach and set_reach:
            assert get_reach == set_reach