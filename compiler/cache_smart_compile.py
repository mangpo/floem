import graph_ir, cache, workspace, desugaring, library
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

def find_last_queue(g, s, t, vis, prev=None):
    if s.name in vis:
        return vis[s.name]
    if s == t:
        return []

    vis[s.name] = False
    q = s.element.special
    if isinstance(q, graph_ir.Queue):
        id = None
        for port_name in q.enq.input2ele:
            prev_name, prev_port = q.enq.input2ele[port_name]
            if prev_name == prev:
                id = int(port_name[3:])
                break

        next_name, next_port = q.deq.output2ele['out' + str(id)]
        ans = dfs_same_thread(g, g.instances[next_name], t, vis, s.name)
        if len(ans) == 0:
            ans = [(q, id, prev)]

    else:
        ans = []
        for inst_name, port in s.output2ele.values():
            next = g.instances[inst_name]
            ret = dfs_same_thread(g, next, t, vis, s.name)
            if ret not in ans:
                ans += ret

    vis[s.name] = ans
    return ans

#
# def transform_get(g, s, t, CacheGet, CacheSetGet, CacheRelease):
#     # 1. Check that get_start and get_end is on the same device.
#     if s.thread in g.thread2process:
#         p1 = g.thread2process[s.thread]
#     else:
#         p1 = 'main'
#     if t.thread in g.thread2process:
#         p2 = g.thread2process[t.thread]
#     else:
#         p2 = 'main'
#     assert p1 == p2, "%s and %s must be running the same device." % (s.name, t.name)
#
#     # 2. Duplicate everything after t if s and t are on different threads (queue in between)
#     API_return = None
#     if s.thread != t.thread:
#         subgraph = g.find_subgraph_list(t.name, [])
#         dup_nodes = reversed(subgraph[:-1])
#         if dup_nodes[-1] in g.API_outputs:
#             API_return = dup_nodes[-1]
#         pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_cache', copy=2)
#
#         hit_start = dup_nodes[0] + '_cache1'  # hit
#         subgraph = g.find_subgraph_list(hit_start, [])
#         for name in subgraph:
#             g.instances[name].thread = s.thread
#
#         rel_after = [dup_nodes[0] + '_cache0', dup_nodes[0] + '_cache1']
#     else:
#         hit_start = t.output2ele['out'][0]
#         rel_after = [hit_start]
#
#     # 3. Insert cache_rel
#     if CacheRelease:
#         cache_rel_inst = CacheRelease(create=False).instance
#         rel_element = cache_rel_inst.element
#         rel_element = rel_element.clone(rel_element.name + "_for_get")
#         g.addElement(rel_element)
#         cache_rel_inst.element = rel_element
#
#         if API_return:
#             # Adjust release element
#             API_instance = g.instances[API_return]
#             types = API_instance.element.outports[0].argtypes
#             args = ['ret{0}'.format(i) for i in range(len(types))]
#             rel_element.inports = [Port('inp', types, rel_element.inports[0].pipeline)]
#             rel_element.outports = [Port('out', types, rel_element.outports[0].pipeline)]
#             rel_element.reassign_input_values('inp', types, args)
#             rel_element.reassign_output_values('out', args)
#
#             # Connect release element
#             g.newElementInstance(cache_rel_inst.element, cache_rel_inst.name, cache_rel_inst.args)
#             g.set_thread(cache_rel_inst.name, s.therad)
#
#             g.connect(API_return, cache_rel_inst.name, API_instance.element.outports[0].name)
#             index = g.API_outputs.index(API_return)
#             g.API_outputs[index] = cache_rel_inst.name
#         else:
#             # Adjust release element
#             rel_element.remove_outport('out')
#
#             # Connect release element
#             for i in range(len(rel_after)):
#                 g.newElementInstance(cache_rel_inst.element, cache_rel_inst.name + str(i), cache_rel_inst.args)
#                 g.set_thread(cache_rel_inst.name+ str(i), node.therad)
#                 node = pipeline_state_join.get_node_before_release_nolive(rel_after, g, '', {})
#                 g.connect(node.name, cache_rel_inst.name, 'release')
#
#     # 4. Insert cache_get
#     cache_get_inst = CacheGet(create=False).instance
#     g.newElementInstance(cache_get_inst.element, cache_get_inst.name, cache_get_inst.args)
#     g.set_thread(cache_get_inst.name, s.thread)
#
#     # replace dummy get_start with real get
#     if len(s.input2ele) > 0:
#         inport = 'inp'
#         l = s.input2ele[inport]
#         while len(l) > 0:
#             prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
#             g.disconnect(prev_name, s.name, prev_port, inport)
#             g.connect(prev_name, cache_get_inst.name, prev_port, 'inp')
#
#     outport = 'out'
#     next_name, next_port = s.output2ele[outport]
#     g.disconnect(s.name, next_name, outport, next_port)
#     g.connect(cache_get_inst.name, next_name, 'miss', next_port)
#     g.connect(cache_get_inst.name, hit_start, 'hit', 'inp')
#
#     g.deleteElementInstance(s.name)
#
#     # 5. Insert cache_set
#     cache_set_inst = CacheSetGet(create=False).instance
#     g.newElementInstance(cache_set_inst.element, cache_set_inst.name, cache_set_inst.args)
#     g.set_thread(cache_set_inst.name, s.thread)
#
#     # replace dummy get_end with real set
#     inport = 'inp'
#     l = t.input2ele[inport]
#     while len(l) > 0:
#         prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
#         g.disconnect(prev_name, t.name, prev_port, inport)
#         g.connect(prev_name, cache_set_inst.name, prev_port, 'inp')
#
#     outport = 'out'
#     next_name, next_port = t.output2ele[outport]
#     g.disconnect(t.name, next_name, outport, next_port)
#     g.connect(cache_set_inst.name, next_name, 'out', next_port)
#
#     g.deleteElementInstance(t.name)
#


def get_element_ports(port):
    return port.spec.element_ports


def transform_get(g, get_start, get_end, get_composite, set_start):
    # A >> get.begin
    if len(get_start.input2ele) > 0:
        ports = get_element_ports(get_composite.inp)
        assert len(ports) == 1
        inp = ports[0]

        l = get_start.input2ele['inp']
        while len(l) > 0:
            prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
            g.disconnect(prev_name, get_start.name, prev_port, 'inp')
            g.connect(prev_name, inp.element.name, prev_port, inp.name)

    # get.query_begin >> GetQuery
    ports = get_element_ports(get_composite.query_begin)
    assert len(ports) == 1
    query_begin = ports[0]

    next_name, next_port = get_start.output2ele['out']
    g.disconnect(get_start.name, next_name, 'out', next_port)
    g.connect(query_begin.element.name, next_name, query_begin.name, next_port)

    # GetQuery >> get.query_end
    ports = get_element_ports(get_composite.query_end)
    assert len(ports) == 1
    query_end = ports[0]

    l = get_end.input2ele['inp']
    while len(l) > 0:
        prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
        g.disconnect(prev_name, get_end.name, prev_port, 'inp')
        g.connect(prev_name, query_end.element.name, prev_port, query_end.name)

    # get.end >> GetQuery
    ports = get_element_ports(get_composite.out)

    next_name, next_port = get_end.output2ele['out']
    g.disconnect(get_end.name, next_name, 'out', next_port)
    for out in ports:
        g.connect(out.element.name, next_name, out.name, next_port)

    # get.evict >> SetQuery
    if set_start:
        subgraph = g.find_subgraph_list(set_start.name, [])
        dup_nodes = reversed(subgraph[:-1])
        pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_get', copy=1)
        start = dup_nodes[0] + '_get0'

        subgraph = g.find_subgraph_list(start, [])
        for name in subgraph:
            g.instances[name].thread = get_start.thread

        g.disconnect(set_start.name, start)
        ports = get_element_ports(get_composite.evict_begin)
        assert len(ports) == 1
        evict_begin = ports[0]
        g.connect(evict_begin.element.name, start, evict_begin.name)

    # 1. Check that get_start and get_end is on the same device.
    if get_start.thread in g.thread2process:
        p1 = g.thread2process[get_start.thread]
    else:
        p1 = 'main'
    if get_end.thread in g.thread2process:
        p2 = g.thread2process[get_end.thread]
    else:
        p2 = 'main'
    assert p1 == p2, "%s and %s must be running the same device." % (get_start.name, get_end.name)

    # 2. Duplicate everything after t if s and t are on different threads (queue in between)
    API_return = None
    if get_start.thread != get_end.thread:
        subgraph = g.find_subgraph_list(get_end.name, [])
        dup_nodes = reversed(subgraph[:-1])
        if dup_nodes[-1] in g.API_outputs:
            API_return = dup_nodes[-1]
        pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_cache', copy=2)

        hit_start = dup_nodes[0] + '_cache0'  # hit
        subgraph = g.find_subgraph_list(hit_start, [])
        for name in subgraph:
            g.instances[name].thread = get_start.thread

    g.deleteElementInstance(get_start.name)
    g.deleteElementInstance(get_end.name)

    # Order release before API return
    if get_composite.release_inst:
        for i in len(g.threads_API):
            api = g.threads_API[i]
            if get_start.thread == api.name:
                out_inst = g.API_outputs[i]
                g.threads_order.append(get_composite.release_inst.name, out_inst)
                break

def transform_set(g, s, t, CacheGet, CacheSet, CacheRelease, cache_high, queues):
    argtypes = s.element.inports['inp'].argtypes
    type_args = []
    args = []

    for i in range(len(argtypes)):
        type_args.append('{0} x{1}'.format(argtypes[i], i))
        args.append('x{0}'.format(i))

    n_out = len(t.element.inports['inp'].argtypes)

    # 1. Disconnect A from s, connect A to cache_set
    cache_set_inst = CacheSet(create=False).instance
    g.newElementInstance(cache_set_inst.element, cache_set_inst.name, cache_set_inst.args)
    g.set_thread(cache_set_inst.name, s.thread)

    if len(s.input2ele) > 0:
        inport = 'inp'
        l = s.input2ele[inport]
        while len(l) > 0:
            prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
            g.disconnect(prev_name, s.name, prev_port, inport)
            g.connect(prev_name, cache_set_inst, prev_port)


    # 2. Write-back
    if cache_high.write_policy == graph_ir.Cache.write_back:
        # 2.1 Connect evict case (write-back & write-allocate)
        if cache_high.write_miss == graph_ir.Cache.write_alloc:
            check_evict_src = r'''
            (%s) = inp();
            bool evict = state->cache_item && state->cache_item->evicted;
            
            output switch { case evict: out(?); }
            ''' % (type_args)

        fill_ele = Element(q.name + "_fill" + str(i), [Port("in_entry", ["q_buffer"]), Port("in_pkt", [])],
                           [Port("out", ["q_buffer"])] + fill_extra_port, fill_src)
        g.addElement(fill_ele)
        fill_inst = ElementInstance(fill_ele.name, prefix + fill_ele.name + "_from_" + in_inst)

        # 2.2 Connect conditional set query (write-back & no-allocate)

        # Then, connect cache_set to B

    # 4. Connect always set query (write-through)



def create_cache(cache_high, set):
    workspace.push_decl()
    workspace.push_scope(cache_high.name)
    GetComposite, SetComposite = \
        cache.cache_default(cache_high.name, cache_high.key_type, cache_high.val_type,
                            var_size=cache_high.var_size, hash_value=cache_high.hash_value,
                            update_func=cache_high.update_func, release_type=[],
                            write_policy=cache_high.write_policy, write_miss=cache_high.write_miss,
                            set_query=set)

    get_composite = GetComposite()
    library.Drop(create=False)

    decl = workspace.pop_decl()
    scope, collection = workspace.pop_scope()
    p = Program(*(decl + scope))
    dp = desugaring.desugar(p)
    g = program_to_graph_pass(dp, default_process='tmp')

    return g, get_composite, library.Drop


def cache_pass(g):
    caches = []
    for instance in g.instances.values():
        c = instance.element.special
        if isinstance(c, graph_ir.Cache):
            if c not in caches:
                caches.append(c)

    for cache_high in caches:
        thread = None
        if cache_high.get_start:
            get_start = g.instances[cache_high.get_start.name]
            get_end = g.instances[cache_high.get_end.name]
            get_reach = dfs_same_thread(g, get_start, get_end, {})
            assert get_start.thread == get_end.thread
            thread = get_start.thread
        else:
            get_start = None
            get_end = None

        if cache_high.set_start:
            set_start = g.instances[cache_high.set_start.name]
            set_end = g.instances[cache_high.set_end.name]
            set_reach = dfs_same_thread(g, set_start, set_end, {})
            assert set_start.thread == set_end.thread
            if thread:
                assert set_start.thread == thread
            else:
                thread = set_start.thread
        else:
            set_start = None
            set_end = None

        if get_reach and set_reach:
            assert get_reach == set_reach

        g_add, get_composite, Drop = create_cache(cache_high, set_start)
        for instance in g_add.instances.values():
            instance.thread = get_start.thread
        g.merge(g_add)

        if set_start and len(set_reach) > 1 and cache_high.write_policy == graph_ir.Cache.write_back:
            queues = find_last_queue(g, set_start, set_end, {})
            (q0, id0, prev0) = queues[0]
            for q, id, prev in queues:
                assert q == q0
                l = q.enq.input2ele['inp' + str(id)]
                while len(l) > 0:
                    prev_name, prev_port = l[0]
                    g.disconnect(prev_name, q.enq.name, prev_port, 'inp' + str(id))

                    drop_inst = Drop(create=False).instance
                    g.newElementInstance(drop_inst.element, drop_inst.name, drop_inst.args)
                    g.set_thread(drop_inst.name, prev.thread)
                    g.connect(prev_name, drop_inst.name, prev_port)

                next_name, next_port = q.enq.output2ele['out' + str(id)]
                g.disconnect(q.deq.name, next_name, 'out' + str(id), next_port)

                subgraph = g.find_subgraph_list(next_name, [])
                for inst_name in subgraph:
                    g.deleteElementInstance(inst_name)
            q0.rename_ports(g)

        if get_start:
            transform_get(g, get_start, get_end, get_composite, set_start)
