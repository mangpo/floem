import queue2, workspace, desugaring
from program import *
from pipeline_state_join import get_node_before_release


def get_entry_content(vars, pipeline_state, g, src2fields):
    # content of struct
    content = " "
    # ending content of struct (for variable-size fields)
    end = ""
    special = {}
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
            content += "%s %s; " % (current_type, fields[-1])
        elif annotation is "shared":
            content += "uint64_t %s; " % fields[-1]  # convert pointer to number
            special[var] = (current_type, fields[-1], "shared", current_info[3])
        elif annotation is "copysize":
            if end is not "":
                raise Exception("Currently do not support copying multiple variable-length fields over smart queue.")
            end = "uint8_t %s[]; " % fields[-1]
            special[var] = (current_type, fields[-1], "copysize", current_info[3])
        else:
            raise Exception("Unknown type annotation '%s' for field '%s' of type '%s'." %
                            (annotation, fields[-1], current_type))
    return content + end, special


def get_state_content(vars, pipeline_state, g, src2fields, special):
    content = " "
    for var in vars:
        fields = src2fields[var]
        current_type = pipeline_state
        for field in fields:
            if current_type[-1] == "*":
                current_type.rstrip('*').rstip()
            current_type = g.states[current_type].mapping[field]
        content += "%s %s; " % (current_type[0], fields[-1])

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
        g.find_subgraph(start_name, subgraph)

        if instance.name in subgraph:
            return state


def create_queue(name, size, n_cores, blocking, enq_atomic, deq_atomic, scan, core):
    workspace.push_decl()
    workspace.push_scope(name)
    EnqAlloc, EnqSubmit, DeqGet, DeqRelease, Scan = \
        queue2.queue_variable_size(name, size, n_cores, blocking, enq_atomic, deq_atomic, scan, core)
    EnqAlloc(create=False)
    EnqSubmit(create=False)
    DeqGet(create=False)
    DeqRelease(create=False)
    if scan:
        Scan(create=False)

    decl = workspace.pop_decl()
    scope, collection = workspace.pop_scope()
    p = Program(*(decl + scope))
    dp = desugaring.desugar(p)
    g = program_to_graph_pass(dp, default_process='tmp')

    return g, EnqAlloc, EnqSubmit, DeqGet, DeqRelease, Scan


def compile_smart_queue(g, q, src2fields):
    pipeline_state = find_pipeline_state(g, q.enq)
    deq_thread = g.get_thread_of(q.deq.name)
    if q.scan:
        scan_thread = g.get_thread_of(q.scan.name)

    if re.match("_impl", q.enq.name):
        prefix = "_impl_"
    elif re.match("_spec", q.enq.name):
        prefix = "_spec_"
    else:
        prefix = ""

    g_add, enq_alloc, enq_submit, deq_get, deq_release, scan = \
        create_queue(q.name, q.size, q.n_cores,
                     blocking=q.blocking, enq_atomic=q.enq_atomic, deq_atomic=q.deq_atomic, scan=q.scan_type, core=True)
    g.merge(g_add)

    # if isinstance(q, queue_ast.QueueVariableSizeOne2Many):
    #     deq_types = ["q_entry*", "size_t"]
    #     deq_src_in = "(q_entry* e, size_t core) = in();"
    #     deq_args_out = "e,core"
    # elif isinstance(q, queue_ast.QueueVariableSizeMany2One):
    #     deq_types = ["q_entry*"]
    #     deq_src_in = "(q_entry* e) = in();"
    #     deq_args_out = "e"

    deq_types = ["q_entry*", "size_t"]
    deq_src_in = "(q_entry* e, size_t core) = in();"
    deq_args_out = "e,core"

    src_cases = ""
    for i in range(q.n_cases):
        src_cases += "    case (type == %d): out%d(%s);\n" % (i + 1, i, deq_args_out)
    src_release = "    case (type == 0): release(e);\n"
    classify_ele = Element(q.deq.name + "_classify", [Port("in", deq_types)],
                           [Port("out" + str(i), deq_types) for i in range(q.n_cases)]
                           + [Port("release", ["q_entry*"])], r'''
        %s
        int type = -1;
        if (e != NULL) type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        output switch {
            %s
        }''' % (deq_src_in, src_cases + src_release))

    scan_classify_ele = Element(q.deq.name + "_scan_classify", [Port("in", deq_types)],
                                [Port("out" + str(i), deq_types) for i in range(q.n_cases)], r'''
        %s
        uint16_t type = 0;
        if (e != NULL) type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        output switch {
            %s
        }''' % (deq_src_in, src_cases))

    g.addElement(classify_ele)
    deq_get_inst = deq_get(q.deq.name + "_get", create=False).instance
    deq_release_inst = deq_release(q.deq.name + "_release", create=False).instance
    classify_inst = ElementInstance(classify_ele.name, classify_ele.name + "_inst")
    new_instances = [deq_get_inst, deq_release_inst, classify_inst]

    if scan:
        g.addElement(scan_classify_ele)
        scan_inst = scan(q.enq.name + "_scan", create=False).instance
        scan_classify_inst = ElementInstance(scan_classify_ele.name, scan_classify_ele.name + "_scan_inst")
        new_instances.append(scan_inst)
        new_instances.append(scan_classify_inst)

    for inst in new_instances:
        g.newElementInstance(inst.element, inst.name, inst.args)
        instance = g.instances[inst.name]
        instance.liveness = set()
        instance.uses = set()

    # Connect deq_get -> classify, classify -> release
    g.connect(deq_get_inst.name, classify_inst.name)
    g.connect(classify_inst.name, deq_release_inst.name, "release")
    if scan:
        g.connect(scan_inst.name, scan_classify_inst.name)

    # Resource
    g.set_thread(deq_get_inst.name, deq_thread)
    g.set_thread(classify_inst.name, deq_thread)
    g.set_thread(deq_release_inst.name, deq_thread)
    if scan:
        g.set_thread(scan_inst.name, scan_thread)
        g.set_thread(scan_classify_inst.name, scan_thread)

    # Memorize connections
    ins_map = []
    out_map = []
    scan_map = []

    for i in range(q.n_cases):
        ins = q.enq.input2ele["inp" + str(i)]
        out = q.deq.output2ele["out" + str(i)]
        ins_map.append(ins)
        out_map.append(out)
        if scan:
            clean = q.scan.output2ele["out" + str(i)]
            scan_map.append(clean)

    # Delete dummy dequeue and enqueue instances
    g.delete_instance(q.enq.name)
    g.delete_instance(q.deq.name)
    if scan:
        g.delete_instance(q.scan.name)

    # Preserve original dequeue connection
    for port in q.deq.input2ele:
        l = q.deq.input2ele[port]
        for prev_inst, prev_port in l:
            if not prev_inst == q.enq.name:
                g.connect(prev_inst, deq_get_inst.name, prev_port, port)

    # Preserve original dequeue connection
    if scan:
        for port in q.scan.input2ele:
            l = q.scan.input2ele[port]
            for prev_inst, prev_port in l:
                g.connect(prev_inst, scan_inst.name, prev_port, port)

    for i in range(q.n_cases):
        live = q.deq.liveness[i]
        uses = q.deq.uses[i]
        extras = uses.difference(live)

        #if isinstance(q, queue_ast.QueueVariableSizeOne2Many) and 'core' in live:
        if 'core' in live:
            live = live.difference(set(['core']))
            extras.add('core')

        ins = ins_map[i]
        out = out_map[i]

        # Create states
        content, special = get_entry_content(live, pipeline_state, g, src2fields)
        state_entry = State("entry_" + q.name + str(i),
                            "uint16_t flags; uint16_t len; " + content)
        state_pipeline = State("pipeline_" + q.name + str(i),
                               state_entry.name + "* entry; " +
                               get_state_content(extras, pipeline_state, g, src2fields, special))
        g.addState(state_entry)
        g.addState(state_pipeline)

        # Create elements
        size_src = "sizeof(%s)" % state_entry.name
        for var in special:
            t, name, special_t, info = special[var]
            if special_t == "copysize":
                size_src += " + %s" % info
        size_core_ele = Element(q.name + "_size_core" + str(i), [Port("in", [])], [Port("out", ["size_t", "size_t"])],
                                r'''output { out(%s, state.core); }''' % size_src)

        fill_src = "%s* e = (%s*) in_entry();\n" % (state_entry.name, state_entry.name)
        for var in live:
            field = get_entry_field(var, src2fields)
            if var in special:
                t, name, special_t, info = special[var]
                if special_t == "shared":
                    fill_src += "e->%s = (uintptr_t) state.%s - (uintptr_t) %s;\n" % (field, var, info)
                elif special_t == "copysize":
                    fill_src += "rte_memcpy(e->%s, state.%s, %s);\n" % (field, var, info)
            else:
                fill_src += "e->%s = state.%s;\n" % (field, var)
        fill_src += "e->flags |= %d << TYPE_SHIFT;\n" % (i+1)
        fill_src += "output { out((q_entry*) e); }"
        fill_ele = Element(q.name + "_fill" + str(i), [Port("in_entry", ["q_entry*"]), Port("in_pkt", [])],
                           [Port("out", ["q_entry*"])], fill_src)  # TODO
        fork = Element(q.name + "_fork" + str(i), [Port("in", [])], [Port("out_size_core", []), Port("out_fill", [])],
                       r'''output { out_size_core(); out_fill(); }''')

        save_src = deq_src_in
        if 'core' in extras:
                save_src += "state.core = core;\n"
        save_src += "state.entry = ({0} *) e;\n".format(state_entry.name)
        for var in special:
            t, name, special_t, info = special[var]
            if special_t == "shared":
                save_src += "state.{0} = (uintptr_t) {1} + (uintptr_t) state.entry->{0};\n".format(name, info)
            elif special_t == "copysize":
                save_src += "state.{0} = state.entry->{0};\n".format(name)
        save_src += "output { out(); }\n"
        save = Element(q.name + "_save" + str(i), [Port("in", deq_types)], [Port("out", [])], save_src)
        g.addElement(size_core_ele)
        g.addElement(fill_ele)
        g.addElement(fork)
        g.addElement(save)

        # Enqueue
        for in_inst, in_port in ins:
            in_thread = g.instances[in_inst].thread

            # Enqueue instances
            enq_alloc_inst = enq_alloc(prefix + q.name + "_enq_alloc" + str(i) + "_from_" + in_inst, create=False).instance
            enq_submit_inst = enq_submit(prefix + q.name + "_enq_submit" + str(i) + "_from_" + in_inst, create=False).instance
            size_core = ElementInstance(size_core_ele.name, prefix + size_core_ele.name + "_from_" + in_inst)
            fill_inst = ElementInstance(fill_ele.name, prefix + fill_ele.name + "_from_" + in_inst)
            fork_inst = ElementInstance(fork.name, prefix + fork.name + "_from_" + in_inst)
            new_instances_live = [enq_alloc_inst, size_core, fill_inst, fork_inst]
            for inst in new_instances_live:
                g.newElementInstance(inst.element, inst.name, inst.args)
                g.set_thread(inst.name, in_thread)
                instance = g.instances[inst.name]
                instance.liveness = live
                instance.uses = uses

            new_instances_nolive = [enq_submit_inst]
            for inst in new_instances_nolive:
                g.newElementInstance(inst.element, inst.name, inst.args)
                g.set_thread(inst.name, in_thread)
                instance = g.instances[inst.name]
                instance.liveness = set()
                instance.uses = set()

            # Enqueue connection
            g.connect(in_inst, fork_inst.name, in_port)
            g.connect(fork_inst.name, size_core.name, "out_size_core")
            g.connect(size_core.name, enq_alloc_inst.name)
            g.connect(enq_alloc_inst.name, fill_inst.name, "out", "in_entry")
            g.connect(fork_inst.name, fill_inst.name, "out_fill", "in_pkt")
            g.connect(fill_inst.name, enq_submit_inst.name)

        # Create deq instances
        save_inst = ElementInstance(save.name, prefix + save.name + "_inst")
        g.newElementInstance(save_inst.element, save_inst.name, save_inst.args)
        g.set_thread(save_inst.name, deq_thread)

        # Set pipeline state
        g.add_pipeline_state(save_inst.name, state_pipeline.name)
        save_inst = g.instances[save_inst.name]
        save_inst.liveness = live
        save_inst.uses = uses
        save_inst.extras = extras
        save_inst.special_fields = special

        # Dequeue connection
        out_inst, out_port = out
        g.connect(classify_inst.name, save_inst.name, "out" + str(i))  # TODO: check else case
        g.connect(save_inst.name, out_inst, "out", out_port)

        # Dequeue release connection
        node = get_node_before_release(out_inst, g, live, prefix)
        g.connect(node.name, deq_release_inst.name, "release")

        if scan:
            # Create scan save
            scan_save_inst = ElementInstance(save.name, prefix + save.name + "_scan_inst")
            g.newElementInstance(scan_save_inst.element, scan_save_inst.name, scan_save_inst.args)
            g.set_thread(scan_save_inst.name, scan_thread)

            scan_save_inst = g.instances[scan_save_inst.name]
            g.add_pipeline_state(scan_save_inst.name, state_pipeline.name)
            scan_save_inst.liveness = live
            scan_save_inst.uses = uses
            scan_save_inst.extras = extras
            scan_save_inst.special_fields = special

            clean_inst, clean_port = scan_map[i]
            g.connect(scan_classify_inst.name, scan_save_inst.name, "out" + str(i))
            g.connect(scan_save_inst.name, clean_inst, "out", clean_port)


def order_smart_queues(name, vis, order, g):
    if name in vis:
        return

    vis.add(name)
    instance = g.instances[name]
    for next_name, next_port in instance.output2ele.values():
        order_smart_queues(next_name, vis, order, g)

    q = instance.element.special
    if q and q.enq == instance:
        order.append(q)


def compile_smart_queues(g, src2fields):
    original_pipeline_states = copy.copy(g.pipeline_states)
    order = []
    vis = set()
    for instance in g.instances.values():
        q = instance.element.special
        if q and q.enq == instance:
            order_smart_queues(q.enq.name, vis, order, g)

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