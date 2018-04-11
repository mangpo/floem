import queue, workspace, desugaring, graph_ir
from program import *
from pipeline_state_join import get_node_before_release, duplicate_subgraph, add_release_entry_port


def filter_live(vars):
    var_list = [v for v in vars]
    var_list = sorted(var_list, key=lambda x: len(x))
    vars = []
    for new_var in var_list:
        add = True
        for var in vars:
            m = re.match(var + '\.', new_var)
            if m:
                add = False
                break
            m = re.match(var + '->', new_var)
            if m:
                add = False
                break
        if add:
            vars.append(new_var)

    return set(vars)


def get_entry_content(vars, pipeline_state, g, src2fields):
    # content of struct
    content = " "
    # ending content of struct (for variable-size fields)
    end = ""
    special = {}
    non_special = {}
    for var in vars:
        fields = src2fields[var]
        current_type = pipeline_state
        current_info = None
        for field in fields:
            if current_type[-1] == "*":
                current_type = current_type.rstrip('*').rstrip()

            try:
                mapping = g.states[current_type].mapping
            except KeyError:
                raise Exception("Undefined state type '%s'." % current_type)
            try:
                current_info = mapping[field]
                current_type = current_info[0]
            except KeyError:
                raise Exception("Field '%s' is undefined in state type '%s'." % (field, current_type))

        annotation = current_info[2]
        if annotation is None:
            non_special[var] = current_type
            content += "%s %s; " % (current_type, fields[-1])
        elif annotation is "shared":
            content += "uint64_t %s; " % fields[-1]  # convert pointer to number
            special[var] = (current_type, fields[-1], "shared", current_info[3])
        elif annotation is "copysize":
            # if end is not "":
            #     raise Exception("Currently do not support copying multiple variable-length fields over smart queue.")
            # if end is "":
            #     end = "uint8_t %s[]; " % fields[-1]
            end = "uint8_t _content[]; "
            special[var] = (current_type, fields[-1], "copysize", current_info[3])
        else:
            raise Exception("Unknown type annotation '%s' for field '%s' of type '%s'." %
                            (annotation, fields[-1], current_type))
    return content + end, special, non_special


def get_state_content(vars, pipeline_state, g, src2fields, special):
    content = " "
    for var in vars:
        fields = src2fields[var]
        current_type = pipeline_state
        for field in fields:
            if current_type[-1] == "*":
                current_type = current_type.rstrip('*').rstrip()
            current_type = g.states[current_type].mapping[field][0]
        content += "%s %s; " % (current_type, fields[-1])

    for var in special:
        t, name, special_t, info = special[var]
        content += "%s %s; " % (t, name)
    return content


def get_entry_field(var, src2fields):
    fields = src2fields[var]
    return fields[-1]


def find_pipeline_state(g, instance):
    for start_name in g.pipeline_states:
        state = g.pipeline_states[start_name]
        subgraph = set()
        g.find_subgraph_with_queue(start_name, subgraph)

        if instance.name in subgraph:
            return state


def create_queue(q, name, entry_size, size, insts, enq_blocking, deq_blocking, enq_atomic, deq_atomic, clean,
                 qid_output, checksum):
    workspace.push_decl()
    workspace.push_scope(name)
    EnqAlloc, EnqSubmit, DeqGet, DeqRelease, clean = \
        queue.queue_default(name, entry_size, size, insts,
                            enq_blocking=enq_blocking, deq_blocking=deq_blocking,
                            enq_atomic=enq_atomic, deq_atomic=deq_atomic,
                            clean=clean, qid_output=qid_output, checksum=checksum)

    EnqAlloc(create=False, configure=[0])
    EnqAlloc(create=False, configure=[q.enq_gap])
    EnqSubmit(create=False)
    DeqGet(create=False)
    DeqRelease(create=False)

    decl = workspace.pop_decl()
    scope, collection = workspace.pop_scope()
    p = Program(*(decl + scope))
    dp = desugaring.desugar(p)
    g = program_to_graph_pass(dp, default_process='tmp')

    return g, EnqAlloc, EnqSubmit, DeqGet, DeqRelease, clean


def need_byte_reverse(g, t1, t2):
    d1 = g.get_device_from_thread(t1)
    d2 = g.get_device_from_thread(t2)

    if d1 == target.CAVIUM and d2 == target.CAVIUM:
        raise Exception("Smart queue is not yet support for communicating within Cavium.")

    return d1 == target.CAVIUM and not d2 == target.CAVIUM


def get_size2convert(g, enq_thread, deq_thread):
    byte_reverse = need_byte_reverse(g, enq_thread, deq_thread)
    if byte_reverse:
        htons = "nic_htons"
        htonl = "nic_htonl"
        htonp = "nic_htonp"
    else:
        htons = ""
        htonl = ""
        htonp = ""

    size2convert = {1: "", 2: htons, 4: htonl, 8: htonp}
    return byte_reverse, size2convert, htons, htonl, htonp


def get_fill_entry_src(g, deq_thread, enq_thread, live, special, extras,
                       state_entry, src2fields, mapping, pipeline_state, i,
                       enq_output):
    byte_reverse, size2convert, htons, htonl, htonp = get_size2convert(g, deq_thread, enq_thread)

    fill_src = "  q_buffer buff = in_entry();\n"
    fill_src += "  %s* e = (%s*) buff.entry;\n" % (state_entry.name, state_entry.name)
    fill_src += "  if(e) {\n"
    copysize = ""
    for var in live:
        field = get_entry_field(var, src2fields)
        if var in special:
            t, name, special_t, info = special[var]
            if special_t == "shared":
                fill_src += "    e->%s = %s((uintptr_t) state.%s - (uintptr_t) %s);\n" % (field, htonp, var, info)
            elif special_t == "copysize":
                assert t[-1] == "*", \
                    "Smart queue: field '%s' of per-packet state '%s' must be a pointer" % (field, pipeline_state)
                # assert t == "void*" or common.sizeof(t[:-1]) == 1, \
                #     "Smart queue: field '%s' of per-packet state '%s' must be a pointer to uint8_t array." % \
                #     (field, pipeline_state)
                #fill_src += "    memcpy(e->%s, state.%s, %s);\n" % (field, var, info)

                fill_src += "    memcpy(e->_content %s, state.%s, %s);\n" % (copysize, var, info)
                copysize += "+ %s" % info
        else:
            try:
                t = mapping[var]
                size = common.sizeof(t)
                convert = size2convert[size]
                if common.is_pointer(t):
                    fill_src += "    e->%s = (%s) %s((uint64_t) state.%s);\n" % (field, t, convert, var)
                else:
                    fill_src += "    e->%s = %s(state.%s);\n" % (field, convert, var)
            except common.UnkownType:
                fill_src += "    e->%s = state.%s;\n" % (field, var)

    fill_src += "    e->task = %d;\n" % (i + 1)
    fill_src += "  }" # end if(e)
    if i == 2:
        fill_src += r'''
        else {
        printf("drop new segment\n");
        }
        '''
    if enq_output:
        fill_src += "  output { out(buff); done(); }"
    else:
        fill_src += "  output { out(buff); }"
    return fill_src


def get_save_state_src(g, deq_thread, enq_thread, live, special, extras,
                       state_entry, src2fields, mapping, pipeline_state, qid=True):
    byte_reverse, size2convert, htons, htonl, htonp = get_size2convert(g, deq_thread, enq_thread)

    if qid:
        save_src = "(q_buffer buff, int qid) = in();"
    else:
        save_src = "(q_buffer buff) = in();"

    if qid and 'qid' in extras:
        save_src += "  state.qid = qid;\n"
    save_src += "  state.buffer = buff;\n"
    save_src += "  state.entry = (%s*) buff.entry;\n" % state_entry.name
    copysize = ""

    order1 = []
    order2 = []
    for var in live:
        if var not in special:
            order1.append(var)
        else:
            order2.append(var)

    for var in order1 + order2:
        field = get_entry_field(var, src2fields)
        if var in special:
            t, name, special_t, info = special[var]
            if special_t == "shared":
                save_src += "  state.{0} = ({3}) ((uintptr_t) {1} + {2}(state.entry->{0}));\n". \
                    format(name, info, htonp, t)
            elif special_t == "copysize":
                assert t[-1] == "*", \
                    "Smart queue: field '%s' of per-packet state '%s' must be a pointer" % (field, pipeline_state)
                # assert t == "void*" or common.sizeof(t[:-1]) == 1, \
                #     "Smart queue: field '%s' of per-packet state '%s' must be a pointer to uint8_t array." % \
                #     (field, pipeline_state)
                #save_src += "  state.{0} = ({1}) state.entry->{0};\n".format(name, t)

                save_src += "  state.{0} = ({1}) (state.entry->_content {2});\n".format(name, t, copysize)
                copysize += "+ %s" % info
        elif byte_reverse:
            try:
                t = mapping[var]
                size = common.sizeof(t)
                convert = size2convert[size]
                if common.is_pointer(t):
                    save_src += "  state.{0} = ({2}) {1}((uint64_t) state.{0});\n".format(var, convert, t)
                else:
                    save_src += "  state.{0} = {1}(state.{0});\n".format(var, convert)
            except common.UnkownType:
                pass

    save_src += "  output { out(); }\n"
    return save_src


def compile_smart_queue(g, q, src2fields):
    pipeline_state = find_pipeline_state(g, q.enq[0])
    enq_thread = g.get_thread_of(q.enq[0].name)
    deq_thread = g.get_thread_of(q.deq.name)
    if q.clean:
        clean_thread = g.get_thread_of(q.clean.name)

    enq_device = g.get_device_from_thread(enq_thread)
    for enq in q.enq:
        t = g.get_thread_of(enq.name)
        assert enq_device == g.get_device_from_thread(t)

    if re.match("_impl", q.deq.name):
        prefix = "_impl_"
    elif re.match("_spec", q.deq.name):
        prefix = "_spec_"
    else:
        prefix = ""

    g_add, enq_alloc, enq_submit, deq_get, deq_release, clean = \
        create_queue(q, q.name, entry_size=q.entry_size, size=q.size, insts=q.insts, enq_blocking=q.enq_blocking,
                     deq_blocking=q.deq_blocking, enq_atomic=q.enq_atomic, deq_atomic=q.deq_atomic, clean=q.clean,
                     qid_output=True, checksum=q.checksum)
    g.merge(g_add)

    deq_types = ["q_buffer", "int"]

    src_cases = ""
    for i in range(q.channels):
        src_cases += "    case (type == %d): out%d(buff,qid);\n" % (i + 1, i)
    src_cases += "    case (type == 0): release(buff);\n"
    classify_ele = Element(q.deq.name + "_classify", [Port("in", deq_types)],
                           [Port("out" + str(i), deq_types) for i in range(q.channels)]
                           + [Port("release", ["q_buffer"])], r'''
       (q_buffer buff, int qid) = in();
        q_entry* e = buff.entry;
        int type = -1;
        if (e != NULL) type = e->task;
        output switch {
            %s
        }''' % src_cases)

    src_cases = ""
    for i in range(q.channels):
        src_cases += "    case (type == %d): out%d(buff);\n" % (i + 1, i)
    scan_classify_ele = Element(q.name + "_scan_classify", [Port("in", ["q_buffer"])],
                                [Port("out" + str(i), ["q_buffer"]) for i in range(q.channels)], r'''
        (q_buffer buff) = in();
        q_entry* e = buff.entry;
        uint16_t type = 0;
        if (e != NULL) type = e->task;
        output switch {
            %s
        }''' % src_cases)

    g.addElement(classify_ele)
    deq_get_inst = deq_get(q.deq.name + "_get", create=False).instance
    deq_release_inst = deq_release(q.deq.name + "_release", create=False).instance
    classify_inst = ElementInstance(classify_ele.name, classify_ele.name + "_inst")
    new_instances = [deq_get_inst, deq_release_inst, classify_inst]

    if clean:
        g.addElement(scan_classify_ele)
        scan_inst = clean.instance
        scan_classify_inst = ElementInstance(scan_classify_ele.name, scan_classify_ele.name + "_inst")
        new_instances.append(scan_inst)
        new_instances.append(scan_classify_inst)

    for inst in new_instances:
        g.newElementInstance(inst.element, inst.name, inst.args)
        instance = g.instances[inst.name]
        instance.liveness = set()
        instance.uses = set()

    g.instances[deq_get_inst.name].core_id = q.deq.core_id

    # Connect deq_get -> classify, classify -> release
    g.connect(deq_get_inst.name, classify_inst.name)
    g.connect(classify_inst.name, deq_release_inst.name, "release")
    if clean:
        g.connect(scan_inst.name, scan_classify_inst.name)

    # Resource
    g.set_thread(deq_get_inst.name, deq_thread)
    g.set_thread(classify_inst.name, deq_thread)
    g.set_thread(deq_release_inst.name, deq_thread)
    if clean:
        g.set_thread(scan_inst.name, clean_thread)
        g.set_thread(scan_classify_inst.name, clean_thread)

    # Memorize connections
    ins_map = []
    out_map = []
    scan_map = []
    enq_done = {}
    enq_gap = {}

    for i in range(q.channels):
        ins = []
        for enq in q.enq:
            if "inp" + str(i) in enq.input2ele:
                add = enq.input2ele["inp" + str(i)]
                ins += add
                for x in ins:
                    if q.enq_output:
                        if "done" not in enq.output2ele:
                            raise Exception("Port 'done' of queue '%s' does not connect to anything." % q.name)
                        enq_done[x] = enq.output2ele["done"]
                    enq_gap[x[0]] = q.enq_gap_map[enq.name]
        ins_map.append(ins)

        out = q.deq.output2ele["out" + str(i)]
        out_map.append(out)
        if clean:
            x = q.clean.output2ele["out" + str(i)]
            scan_map.append(x)

    # Delete dummy dequeue and enqueue instances
    for enq in q.enq:
        g.delete_instance(enq.name)
    g.delete_instance(q.deq.name)
    if clean:
        g.delete_instance(q.clean.name)

    # Preserve original dequeue connection
    q_enq_names = [x.name for x in q.enq]
    for port in q.deq.input2ele:
        l = q.deq.input2ele[port]
        for prev_inst, prev_port in l:
            if prev_inst not in q_enq_names:
                g.connect(prev_inst, deq_get_inst.name, prev_port, port)

    # Preserve original clean connection
    if clean:
        for port in q.clean.input2ele:
            l = q.clean.input2ele[port]
            for prev_inst, prev_port in l:
                g.connect(prev_inst, scan_inst.name, prev_port, port)

    save_inst_names = []
    lives = []

    release_vis = set()
    for i in range(q.channels):
        live = filter_live(q.deq.liveness[i])
        uses = filter_live(q.deq.uses[i])
        extras = uses.difference(live)
        qid_uses = copy.copy(uses).union(set(['qid']))
        save_uses = copy.copy(uses).union(set(['buffer']))

        if 'qid' in live:
            live = live.difference(set(['qid']))
            extras.add('qid')

        ins = ins_map[i]
        out = out_map[i]

        # Create states
        content, special, mapping = get_entry_content(live, pipeline_state, g, src2fields)
        state_entry = State("entry_" + q.name + str(i),
                            "uint8_t flag; uint8_t task; uint16_t len; uint8_t checksum; uint8_t pad; " + content)
        state_pipeline = State("pipeline_" + q.name + str(i),
                               "q_buffer buffer; %s* entry;" % state_entry.name +
                               get_state_content(extras, pipeline_state, g, src2fields, special))
        g.addState(state_entry)
        g.addState(state_pipeline)

        # Create element: size
        size_src = "sizeof(%s)" % state_entry.name
        for var in special:
            t, name, special_t, info = special[var]
            if special_t == "copysize":
                size_src += " + %s" % info
        size_qid_ele = Element(q.name + "_size_qid" + str(i), [Port("in", [])], [Port("out", ["int", "int"])],
                                r'''output { out(%s, state.qid); }''' % size_src)

        # Create element: fill
        fill_src = get_fill_entry_src(g, enq_thread, deq_thread, live, special, extras,
                                      state_entry, src2fields, mapping, pipeline_state, i, q.enq_output)
        fill_extra_port = [Port("done", [])] if q.enq_output else []
        fill_ele = Element(q.name + "_fill" + str(i), [Port("in_entry", ["q_buffer"]), Port("in_pkt", [])],
                           [Port("out", ["q_buffer"])] + fill_extra_port, fill_src)
        fork = Element(q.name + "_fork" + str(i), [Port("in", [])], [Port("out_size_qid", []), Port("out_fill", [])],
                       r'''output { out_size_qid(); out_fill(); }''')

        # Create element: save
        save_src = get_save_state_src(g, deq_thread, enq_thread, live, special, extras,
                                      state_entry, src2fields, mapping, pipeline_state, qid=True)
        save = Element(q.name + "_save" + str(i), [Port("in", deq_types)], [Port("out", [])], save_src)
        g.addElement(size_qid_ele)
        g.addElement(fill_ele)
        g.addElement(fork)
        g.addElement(save)

        # Enqueue
        for in_inst, in_port in ins:
            in_thread = g.instances[in_inst].thread
            gap = enq_gap[in_inst]

            # Enqueue instances
            enq_alloc_inst = enq_alloc(prefix + q.name + "_enq_alloc" + str(i) + "_from_" + in_inst,
                                       create=False, configure=[gap]).instance
            enq_submit_inst = enq_submit(prefix + q.name + "_enq_submit" + str(i) + "_from_" + in_inst, create=False).instance
            size_qid = ElementInstance(size_qid_ele.name, prefix + size_qid_ele.name + "_from_" + in_inst)
            fill_inst = ElementInstance(fill_ele.name, prefix + fill_ele.name + "_from_" + in_inst)
            fork_inst = ElementInstance(fork.name, prefix + fork.name + "_from_" + in_inst)
            new_instances_live = [enq_alloc_inst, size_qid, fill_inst, fork_inst]
            for inst in new_instances_live:
                g.newElementInstance(inst.element, inst.name, inst.args)
                g.set_thread(inst.name, in_thread)
                instance = g.instances[inst.name]
                instance.liveness = live
                instance.uses = uses
            g.instances[size_qid.name].uses = qid_uses
            g.instances[fork_inst.name].uses = qid_uses

            new_instances_nolive = [enq_submit_inst]
            for inst in new_instances_nolive:
                g.newElementInstance(inst.element, inst.name, inst.args)
                g.set_thread(inst.name, in_thread)
                instance = g.instances[inst.name]
                instance.liveness = set()
                instance.uses = set()

            # Enqueue connection
            g.connect(in_inst, fork_inst.name, in_port)
            g.connect(fork_inst.name, size_qid.name, "out_size_qid")
            g.connect(size_qid.name, enq_alloc_inst.name)
            g.connect(enq_alloc_inst.name, fill_inst.name, "out", "in_entry")
            g.connect(fork_inst.name, fill_inst.name, "out_fill", "in_pkt")
            g.connect(fill_inst.name, enq_submit_inst.name, "out")

            if q.enq_output:
                done = enq_done[(in_inst, in_port)]
                g.connect(fill_inst.name, done[0], "done", done[1])

        # Create deq instances
        save_inst = ElementInstance(save.name, prefix + save.name + "_inst")
        g.newElementInstance(save_inst.element, save_inst.name, save_inst.args)
        g.set_thread(save_inst.name, deq_thread)

        # Set pipeline state
        g.add_pipeline_state(save_inst.name, state_pipeline.name)
        save_inst = g.instances[save_inst.name]
        save_inst.liveness = live
        save_inst.uses = save_uses
        save_inst.extras = extras
        save_inst.special_fields = special

        # Dequeue connection
        out_inst, out_port = out
        g.connect(classify_inst.name, save_inst.name, "out" + str(i))  # TODO: check else case
        g.connect(save_inst.name, out_inst, "out", out_port)

        # Dequeue release connection
        lives.append(live)
        save_inst_names.append(save_inst.name)
        add_release_entry_port(g, save_inst)
        g.connect(save_inst.name, deq_release_inst.name, "release")

        if clean:
            # Create scan save
            scan_save_src = get_save_state_src(g, clean_thread, enq_thread, live, special, extras,
                                               state_entry, src2fields, mapping, pipeline_state, qid=False)
            scan_save = Element(q.name + "_scan_save" + str(i), [Port("in", ["q_buffer"])], [Port("out", [])],
                                scan_save_src)
            scan_save_inst = ElementInstance(scan_save.name, prefix + scan_save.name + "_inst")
            g.addElement(scan_save)
            g.newElementInstance(scan_save_inst.element, scan_save_inst.name, scan_save_inst.args)
            g.set_thread(scan_save_inst.name, clean_thread)

            scan_save_inst = g.instances[scan_save_inst.name]
            g.add_pipeline_state(scan_save_inst.name, state_pipeline.name)
            scan_save_inst.liveness = live
            scan_save_inst.uses = save_uses
            scan_save_inst.extras = extras
            scan_save_inst.special_fields = special

            clean_inst, clean_port = scan_map[i]
            g.connect(scan_classify_inst.name, scan_save_inst.name, "out" + str(i))
            g.connect(scan_save_inst.name, clean_inst, "out", clean_port)

    # Insert release dequeue
    # duplicate_overlapped(g, save_inst_names)

    # for i in range(q.channels):
    #     node = get_node_before_release(save_inst_names[i], g, lives[i], prefix, release_vis)
    #     if node not in release_vis:
    #         release_vis.add(node)
    #         g.connect(node.name, deq_release_inst.name, "release")


def code_change(instance):
    return len(instance.uses) > 0


def duplicate_overlapped(g, save_inst_names):
    parents = {}
    for instance in g.instances.values():
        parents[instance.name] = []

    global_list = []
    for i in range(len(save_inst_names)):
        start_name = save_inst_names[i]
        subgraph = g.find_subgraph_list(start_name, [])

        for inst_name in subgraph:
            parents[inst_name].append(start_name)

        for x in reversed(subgraph):
            if x not in global_list:
                global_list.append(x)

    filtered_list = [x for x in global_list if (len(parents[x]) > 1) and (x not in g.API_outputs)]
    duplicate_subgraph(g, filtered_list)


def order_smart_queues(name, vis, order, g):
    if name in vis:
        return

    vis.add(name)
    instance = g.instances[name]
    for next_name, next_port in instance.output2ele.values():
        order_smart_queues(next_name, vis, order, g)

    q = instance.element.special
    if isinstance(q, graph_ir.Queue) and (instance in q.enq) and (q not in order):
        order.append(q)

def compute_enqueue_gap(g, q):
    gap_map = {}
    if len(q.enq) == 1:
        gap_map[q.enq[0].name] = 0
    else:
        reachable = g.find_subgraph_with_queue(q.deq.name, set())
        need_gap = False
        for enq in q.enq:
            gap_map[enq.name] = 0
            if enq.name in reachable:
                need_gap = True
                break

        if need_gap:
            for enq in q.enq:
                if enq.name not in reachable:
                    gap_map[enq.name] = q.enq_gap

    q.enq_gap_map = gap_map


def compile_smart_queues(g, src2fields):
    original_pipeline_states = copy.copy(g.pipeline_states)
    order = []
    vis = set()
    for instance in g.instances.values():
        q = instance.element.special
        if isinstance(q, graph_ir.Queue) and instance in q.enq:
            order_smart_queues(instance.name, vis, order, g)

    for q in order:
        compute_enqueue_gap(g, q)

    for q in order:
        compile_smart_queue(g, q, src2fields)

    compress_id = 0
    for inst_name in original_pipeline_states:
        state = g.pipeline_states[inst_name]
        state_obj = g.states[state]
        mapping = state_obj.mapping
        if mapping is None:
            continue

        instance = g.instances[inst_name]

        for var in instance.uses:
            has = False
            for field in mapping:
                m = re.match(field, var)
                if m:
                    has = True
                    break
            if not has:
                raise Exception("Per-packet state '%s' does not contain field '%s'." % (state, var))

        new_state = state + "_compressed" + str(compress_id)
        compress_id += 1
        content = ""

        for i in range(len(state_obj.fields)):
            var = state_obj.fields[i]
            for use in instance.uses:
                m = re.match(var, use)
                if m:
                    content += "%s %s;\n" % (mapping[var][0], var)
                    break

        if state_obj.init:
            inits = []
            for i in range(len(state_obj.fields)):
                var = state_obj.fields[i]
                init = state_obj.init[i]
                for use in instance.uses:
                    m = re.match(var, use)
                    if m:
                        inits.append(init)
                        break
        else:
            inits = None

        state_pipeline = State(new_state, content, inits)
        g.addState(state_pipeline)
        g.pipeline_states[inst_name] = new_state
