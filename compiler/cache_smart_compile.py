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
        for enq in q.enq:
            for port_name in enq.input2ele:
                l = enq.input2ele[port_name]
                for prev_name, prev_port in l:
                    if prev_name == prev:
                        id = int(port_name[3:])
                        break
                if id:
                    break
            if id:
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
        for enq in q.enq:
            for port_name in enq.input2ele:
                l = enq.input2ele[port_name]
                for prev_name, prev_port in l:
                    if prev_name == prev:
                        id = int(port_name[3:])
                        break
                if id:
                    break
            if id:
                break

        next_name, next_port = q.deq.output2ele['out' + str(id)]
        ans = find_last_queue(g, g.instances[next_name], t, vis, s.name)
        if len(ans) == 0:
            ans = [(q, id, prev)]

    else:
        ans = []
        for inst_name, port in s.output2ele.values():
            next = g.instances[inst_name]
            ret = find_last_queue(g, next, t, vis, s.name)
            if ret not in ans:
                ans += ret

    vis[s.name] = ans
    return ans


def get_element_ports(port):
    return port.spec.element_ports


def transform_get(g, get_start, get_end, get_composite, set_start, Drop, write_policy, enq_out):
    # get.enq_out >> enq_out
    ports = get_element_ports(get_composite.enq_out)
    assert len(ports) == 1
    compo_enq_out = ports[0]
    g.connect(compo_enq_out.element.name, enq_out[0], compo_enq_out.name, enq_out[1])

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

    # get.end >> B
    ports = get_element_ports(get_composite.out)

    next_name, next_port = get_end.output2ele['out']
    g.disconnect(get_end.name, next_name, 'out', next_port)
    for out in ports:
        g.connect(out.element.name, next_name, out.name, next_port)
    B = next_name

    # get.evict >> SetQuery
    if write_policy == graph_ir.Cache.write_back and set_start:
        dup_nodes = g.find_subgraph_list(set_start.name, [])
        dup_nodes = dup_nodes[:-1]

        ports = get_element_ports(get_composite.evict_begin)
        assert len(ports) == 1
        evict_begin = ports[0]

        if len(dup_nodes) > 0:
            dup_nodes.reverse()
            pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_get', copy=2)
            start = dup_nodes[0] + '_get1'

            subgraph = g.find_subgraph_list(start, [])
            for name in subgraph:
                g.instances[name].thread = get_start.thread

            g.connect(evict_begin.element.name, start, evict_begin.name)
        else:
            drop_inst = Drop(create=False).instance
            g.newElementInstance(drop_inst.element, drop_inst.name, drop_inst.args)
            g.set_thread(drop_inst.name, get_start.thread)
            g.connect(evict_begin.element.name, drop_inst.name, evict_begin.name)

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
        dup_nodes = g.find_subgraph_list(B, [])
        dup_nodes.reverse()
        # if dup_nodes[-1] in g.API_outputs:
        #     API_return = dup_nodes[-1]
        pipeline_state_join.duplicate_subgraph(g, dup_nodes, suffix='_cache', copy=2)

        hit_start = dup_nodes[0] + '_cache1'  # hit
        subgraph = g.find_subgraph_list(hit_start, [])
        for name in subgraph:
            g.instances[name].thread = get_start.thread

        subgraph = g.find_subgraph_list(query_end.element.name, [])
        for name in subgraph:
            g.instances[name].thread = get_end.thread

    g.deleteElementInstance(get_start.name)
    g.deleteElementInstance(get_end.name)

    # Order release before API return
    # if get_composite.release_inst:
    #     for i in range(len(g.threads_API)):
    #         api = g.threads_API[i]
    #         if get_start.thread == api.name:
    #             out_inst = g.API_outputs[i]
    #             g.threads_order.append(get_composite.release_inst.name, out_inst)
    #             break


def transform_set_write_back(g, set_start, set_end, set_composite, enq_out):
    # set.enq_out >> enq_out
    ports = get_element_ports(set_composite.enq_out)
    assert len(ports) == 1
    compo_enq_out = ports[0]
    g.connect(compo_enq_out.element.name, enq_out[0], compo_enq_out.name, enq_out[1])

    # A >> set.begin
    if len(set_start.input2ele) > 0:
        ports = get_element_ports(set_composite.inp)
        assert len(ports) == 1
        inp = ports[0]

        l = set_start.input2ele['inp']
        while len(l) > 0:
            prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
            g.disconnect(prev_name, set_start.name, prev_port, 'inp')
            g.connect(prev_name, inp.element.name, prev_port, inp.name)

    # get.query_begin >> SetQuery
    ports = get_element_ports(set_composite.query_begin)
    assert len(ports) == 1
    query_begin = ports[0]

    next_name, next_port = set_start.output2ele['out']
    g.disconnect(set_start.name, next_name, 'out', next_port)
    g.connect(query_begin.element.name, next_name, query_begin.name, next_port)

    # get.end >> B
    ports = get_element_ports(set_composite.out)

    next_name, next_port = set_end.output2ele['out']
    g.disconnect(set_end.name, next_name, 'out', next_port)
    for out in ports:
        g.connect(out.element.name, next_name, out.name, next_port)

    subgraph = g.find_subgraph_list(next_name, [])
    for name in subgraph:
        g.instances[name].thread = set_start.thread

    g.deleteElementInstance(set_start.name)
    g.deleteElementInstance(set_end.name)

    # Duplicate if an instance has inputs from get and set on different threads.
    already_dups = []
    for name in subgraph:
        if name in already_dups:
            continue
        instance = g.instances[name]
        thread_list = []
        for port_list in instance.input2ele.values():
            inst_list = [g.instances[prev_name] for (prev_name, prev_port) in port_list]
            thread_list += [inst.thread for inst in inst_list]

        n_threads = len(set(thread_list))

        if n_threads > 1:
            dup_nodes = g.find_subgraph_list(instance.name, [])
            dup_nodes.reverse()
            already_dups += dup_nodes
            l = [t for t in set(thread_list)]
            pipeline_state_join.duplicate_subgraph_wrt_threads(g, dup_nodes, l, suffix='_getset')

    # Does not work for API.


def transform_set_write_through(g, set_start, set_end, set_composite, enq_out):
    # set.enq_out >> enq_out
    ports = get_element_ports(set_composite.enq_out)
    assert len(ports) == 1
    compo_enq_out = ports[0]
    g.connect(compo_enq_out.element.name, enq_out[0], compo_enq_out.name, enq_out[1])

    # A >> set.begin
    if len(set_start.input2ele) > 0:
        ports = get_element_ports(set_composite.inp)
        assert len(ports) == 1
        inp = ports[0]

        l = set_start.input2ele['inp']
        while len(l) > 0:
            prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
            g.disconnect(prev_name, set_start.name, prev_port, 'inp')
            g.connect(prev_name, inp.element.name, prev_port, inp.name)

    # set.query_begin >> SetQuery
    ports = get_element_ports(set_composite.query_begin)

    next_name, next_port = set_start.output2ele['out']
    g.disconnect(set_start.name, next_name, 'out', next_port)
    for out in ports:
        g.connect(out.element.name, next_name, out.name, next_port)

    # SetQuery >> set.query_end
    ports = get_element_ports(set_composite.query_end)
    assert len(ports) == 1
    query_end = ports[0]

    l = set_end.input2ele['inp']
    while len(l) > 0:
        prev_name, prev_port = l[0]  # index = 0 because l is mutated (first element is popped).
        g.disconnect(prev_name, set_end.name, prev_port, 'inp')
        g.connect(prev_name, query_end.element.name, prev_port, query_end.name)

    # set.end >> B
    ports = get_element_ports(set_composite.out)

    next_name, next_port = set_end.output2ele['out']
    g.disconnect(set_end.name, next_name, 'out', next_port)
    for out in ports:
        g.connect(out.element.name, next_name, out.name, next_port)

    subgraph = g.find_subgraph_list(query_end.element.name, [])
    for name in subgraph:
        g.instances[name].thread = set_end.thread

    g.deleteElementInstance(set_start.name)
    g.deleteElementInstance(set_end.name)


def create_cache(cache_high, get, set):
    workspace.push_decl()
    workspace.push_scope(cache_high.name)
    GetComposite, SetComposite = \
        cache.cache_default(cache_high.name, cache_high.key_type, cache_high.val_type,
                            state=cache_high.state, key_name=cache_high.key_name, val_names=cache_high.val_names,
                            keylen_name=cache_high.keylen_name, vallen_name=cache_high.vallen_name,
                            var_size=cache_high.var_size, hash_value=cache_high.hash_value,
                            update_func=cache_high.update_func,
                            write_policy=cache_high.write_policy, write_miss=cache_high.write_miss,
                            set_query=set)

    get_composite = None
    set_composite = None
    if get:
        get_composite = GetComposite()
    if set:
        set_composite = SetComposite()

    decl = workspace.pop_decl()
    scope, collection = workspace.pop_scope()
    p = Program(*(decl + scope))
    dp = desugaring.desugar(p)
    g = program_to_graph_pass(dp, default_process='tmp')

    for instance in g.instances.values():
        if instance.name.find(GetComposite.__name__) >= 0:
            instance.thread = get.thread
        else:
            instance.thread = set.thread

    return g, get_composite, set_composite, library.Drop


def cache_pass(g):
    # g.print_graphviz()

    caches = []
    for instance in g.instances.values():
        c = instance.element.special
        if isinstance(c, graph_ir.Cache):
            if c not in caches:
                caches.append(c)

    for cache_high in caches:
        if cache_high.get_start:
            get_start = g.instances[cache_high.get_start.name]
            get_end = g.instances[cache_high.get_end.name]
            get_queues = []
            get_reach = dfs_same_thread(g, get_start, get_end, {}, queues=get_queues)
            assert g.process_of_thread(get_start.thread) == g.process_of_thread(get_end.thread)
        else:
            get_start = None
            get_end = None
            get_reach = None
            get_queues = None

        if cache_high.set_start:
            set_start = g.instances[cache_high.set_start.name]
            set_end = g.instances[cache_high.set_end.name]
            set_queues = []
            set_reach = dfs_same_thread(g, set_start, set_end, {}, queues=set_queues)
            assert g.process_of_thread(set_start.thread) == g.process_of_thread(set_end.thread)
        else:
            set_start = None
            set_end = None
            set_reach = None
            set_queues = None

        if get_reach and set_reach:
            n = min(len(get_reach), len(set_reach))
            if n > 1:
                n -= 1
                assert get_reach[:n] == set_reach[:n]

        g_add, get_composite, set_composite, Drop = create_cache(cache_high, get_start, set_start)
        g.merge(g_add)

        # Enq output
        enq_out = None

        if get_queues or set_queues:
            in_queue = None
            if get_queues and set_queues:
                if len(get_queues) > 0 and len(set_queues) > 0:
                    assert get_queues[0] == set_queues[0]
                    in_queue = get_queues[0]
                else:
                    assert len(get_queues) == 0 and len(set_queues == 0)
            elif get_queues:
                if len(get_queues) > 0:
                    in_queue = get_queues[0]
            elif set_queues:
                if len(set_queues) > 0:
                    in_queue = set_queues[0]

            if in_queue:
                if 'done' in in_queue.enq[0].output2ele:
                    inst_name, port_name = in_queue.enq[0].output2ele['done']
                    enq_out = (inst_name, port_name)
                    for enq in in_queue.enq:
                        g.disconnect(enq.name, inst_name, 'done', port_name)

                    in_queue.enq_output = False

        if enq_out is None:
            drop_inst = Drop(create=False).instance
            g.newElementInstance(drop_inst.element, drop_inst.name, drop_inst.args)
            g.set_thread(drop_inst.name, prev.thread)
            enq_out = (drop_inst.name, 'inp')


        # Remove connection at set_end for write-back policy
        if set_start and len(set_reach) > 1 and cache_high.write_policy == graph_ir.Cache.write_back:
            queues = find_last_queue(g, set_start, set_end, {})
            (q0, id0, prev0) = queues[0]
            for q, id, prev in queues:
                assert q == q0
                for enq in q.enq:
                    if 'inp' + str(id) in enq.input2ele:
                        l = enq.input2ele['inp' + str(id)]
                        while len(l) > 0:
                            prev_name, prev_port = l[0]
                            prev = g.instances[prev_name]
                            g.disconnect(prev_name, enq.name, prev_port, 'inp' + str(id))

                            if q.enq_output:
                                done_name, done_part = enq.output2ele['done']
                                g.connect(prev_name, done_name, prev_port, done_part)
                            else:
                                drop_inst = Drop(create=False).instance
                                g.newElementInstance(drop_inst.element, drop_inst.name, drop_inst.args)
                                g.set_thread(drop_inst.name, prev.thread)
                                g.connect(prev_name, drop_inst.name, prev_port)

                next_name, next_port = q.deq.output2ele['out' + str(id)]
                g.disconnect(q.deq.name, next_name, 'out' + str(id), next_port)

                set_end.input2ele = {}
                subgraph = g.find_subgraph_list(next_name, [], set_end.name)
                for inst_name in subgraph:
                    g.deleteElementInstance(inst_name, force=True)
            q0.rename_ports(g)
        elif set_start and cache_high.write_policy == graph_ir.Cache.write_back:
            l = set_end.input2ele['inp']
            while len(l) > 0:
                prev_name, prev_port = l[0]
                prev = g.instances[prev_name]
                g.disconnect(prev_name, set_end.name, prev_port, 'inp')
                drop_inst = Drop(create=False).instance
                g.newElementInstance(drop_inst.element, drop_inst.name, drop_inst.args)
                g.set_thread(drop_inst.name, prev.thread)
                g.connect(prev_name, drop_inst.name, prev_port)

        # Graph transformation
        if get_start:
            transform_get(g, get_start, get_end, get_composite, set_start, Drop, cache_high.write_policy, enq_out)
        if set_start:
            if cache_high.write_policy==graph_ir.Cache.write_back:
                transform_set_write_back(g, set_start, set_end, set_composite, enq_out)
            else:
                transform_set_write_through(g, set_start, set_end, set_composite, enq_out)

        # print "------------------------- adding cache --------------------------"
        # g.print_graphviz()
