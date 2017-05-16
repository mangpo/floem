import queue_ast
from program import *
from pipeline_state_join import get_node_before_release
from join_handling import annotate_join_info


def allocate_pipeline_state(element, state):
    add = '  {0} *_state = ({0} *) malloc(sizeof({0}));\n'.format(state)
    element.code = add + element.code


def insert_pipeline_state(element, state, start):
    no_state = True
    if not start:
        for port in element.inports:
            if len(port.argtypes) == 0:
                port.argtypes.append(state + "*")
                if no_state:
                    m = re.search('[^a-zA-Z0-9_](' + port.name + ')\(', element.code)
                    if m:
                        add = '%s *_state = ' % state
                        element.code = element.code[:m.start(1)] + add + element.code[m.start(1):]
                    else:
                        add = '  %s *_state = %s();\n' % (state, port.name)
                        element.code = add + element.code
                    no_state = False

    for port in element.outports:
        if len(port.argtypes) == 0:
            port.argtypes.append(state + "*")
            if element.output_fire == "all":
                element.output_code[port.name] = '%s(_state)' % port.name
            else:
                for i in range(len(element.output_code)):
                    case, code = element.output_code[i]
                    m = re.search(port.name + '\(', code)
                    if m:
                        code = code[:m.end(0)] + '_state' + code[m.end(0):]
                        element.output_code[i] = (case, code)

    element.code = element.code.replace('state.', '_state->')
    if element.output_fire == "all":
        for port in element.output_code:
            code = element.output_code[port]
            code = code.replace('state.', '_state->')
            element.output_code[port] = code
    else:
        for i in range(len(element.output_code)):
            case, code = element.output_code[i]
            code = code.replace('state.', '_state->')
            case = case.replace('state.', '_state->')
            element.output_code[i] = (case, code)


def need_replacement(element, live, extras):
    vars = live.union(extras)
    for var in vars:
        pos = element.code.find(var)
        if pos >= 0:
            return True

        if element.output_fire == "all":
            for out_code in element.output_code.values():
                pos = out_code.find(var)
                if pos >= 0:
                    return True
        else:
            for case, out_code in element.output_code:
                pos = case.find(var)
                if pos >= 0:
                    return True
                pos = out_code.find(var)
                if pos >= 0:
                    return True
    return False


def replace_var(element, var, src2fields, prefix):
    new_var = prefix + src2fields[var][-1]
    element.code = element.code.replace(var, new_var)

    if element.output_fire == "all":
        for port in element.output_code:
            code = element.output_code[port]
            element.output_code[port] = code.replace(var, new_var)
    else:
        for i in range(len(element.output_code)):
            case, out_code = element.output_code[i]
            case = case.replace(var, new_var)
            out_code = out_code.replace(var, new_var)
            element.output_code[i] = (case, out_code)


def replace_states(element, live, extras, src2fields):
    for var in live:
        replace_var(element, var, src2fields, "entry->")

    for var in extras:
        replace_var(element, var, src2fields, "")


def rename_references(g, src2fields):
    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    for start_name, state in g.pipeline_states:
        instance = g.instances[start_name]
        if instance.extras is not None:
            subgraph = set()
            g.find_subgraph(start_name, subgraph)

            for inst_name in subgraph:
                child = g.instances[inst_name]
                element = child.element
                if need_replacement(element, instance.liveness, instance.extras):
                    if len(ele2inst[element.name]) == 1:
                        replace_states(element, instance.liveness, instance.extras, src2fields)
                    else:
                        new_element = element.clone(inst_name + "_with_state_at_" + instance.name)
                        replace_states(new_element, instance.liveness, instance.extras, src2fields)
                        g.addElement(new_element)
                        child.element = new_element


def insert_pipeline_states(g):
    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    for start_name, state in g.pipeline_states:
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        # Allocate state
        instance = g.instances[start_name]
        element = instance.element
        if len(ele2inst[element.name]) == 1:
            allocate_pipeline_state(element, state)
        else:
            new_element = element.clone(start_name + "_with_state_alloc")
            allocate_pipeline_state(new_element, state)
            g.addElement(new_element)
            instance.element = new_element
            ele2inst[new_element.name] = [start_name]

        # Pass state pointers
        vis = set()
        for inst_name in subgraph:
            child = g.instances[inst_name]
            element = child.element
            # If multiple instances can share the same element, make sure we don't modify an element more than once.
            if element.name not in vis:
                vis.add(element.name)
                if len(ele2inst[element.name]) == 1:
                    # TODO: modify element: empty port -> send state*
                    insert_pipeline_state(element, state, inst_name == start_name)
                else:
                    # TODO: create new element: empty port -> send state*
                    new_element = element.clone(inst_name + "_with_state")
                    vis.add(new_element.name)
                    insert_pipeline_state(new_element, state, inst_name == start_name)
                    g.addElement(new_element)
                    child.element = new_element


def find_all_fields(code):
    """
    :param code: string starting with . (. in state.<field>)
    :return: src = (.<field>)+, a list of field, the rest of code after fields
    """
    src = ""
    fields = []
    while True:
        m = re.search('[^a-zA-Z0-9_]', code)
        if m.group(0) == '.':
            field = code[:m.start(0)]
            src += field + '.'
            code = code[m.end(0):]
            fields.append(field)
        elif m.group(0) == '-' and code[m.start(0) + 1] == '>':
            field = code[:m.start(0)]
            src += field + '->'
            code = code[m.end(0) + 1:]
            fields.append(field)
        else:
            field = code[:m.start(0)]
            src += field
            code = code[m.start(0):]
            fields.append(field)
            return src, fields, code


def find_next_def_use(code):
    m = re.search('[^a-zA-Z0-9_]state\.', code)
    if not m:
        return None, None, None, None

    src, fields, code = find_all_fields(code[m.end(0):])

    use = True
    m = re.search('[^ ]', code)
    if m.group() == '=':
        if code[m.start()+1] is not '=':
            use = False

    return src, fields, use, code


def collect_defs_uses(g):
    src2fields = {}
    for element in g.elements.values():
        code = element.code
        while code:
            src, fields, is_use, code = find_next_def_use(code)
            if src:
                src2fields[src] = fields
                if is_use:
                    element.uses.add(src)
                else:
                    element.defs.add(src)

    return src2fields


# def bypass_queue(inst, from_inst):
#     if not isinstance(inst.element.special, queue_smart.Queue):
#         return inst
#
#     for port in inst.output2ele:
#         insts = inst.output2ele[port]
#         if from_inst.name in insts:
#             no = port[3:]
#             port_in = "in" + no
#             insts_in = inst.input2ele[port_in]
#             return insts_in


def analyze_fields_liveness_instance(g, name, in_port):
    instance = g.instances[name]

    # Smart queue
    q = instance.element.special
    if q:
        no = int(in_port[2:])
        if instance.liveness:
            return instance.liveness[no], instance.uses[no]

        instance.liveness = {}
        instance.uses = {}
        deq = q.deq
        for i in range(q.n_cases):
            out_port = "out" + str(i)
            next_name, next_port = deq.output2ele[out_port]
            ret_live, ret_uses = analyze_fields_liveness_instance(g, next_name, next_port)
            instance.liveness[i] = ret_live
            instance.uses[i] = ret_live  # TODO: between queue, only keep live values

        return instance.liveness[no], instance.uses[no]

    # Other elements
    if instance.uses:
        # visited
        if instance.dominants:
            return set(), instance.uses
        else:
            return instance.liveness, instance.uses

    # Union its children
    live = set()
    uses = set()
    for out_port in instance.output2ele:
        next_name, next_port = instance.output2ele[out_port]
        ret_live, ret_uses = analyze_fields_liveness_instance(g, next_name, next_port)
        live = live.union(ret_live)
        uses = uses.union(ret_uses)

    # Union live from join node
    if instance.liveness:
        live = live.union(instance.liveness)

    # - kills + uses
    live = live.difference(instance.element.defs)
    live = live.union(instance.element.uses)
    uses = uses.union(instance.element.defs)
    uses = uses.union(instance.element.uses)
    instance.liveness = live
    instance.uses = uses

    # Handle join element
    if instance.dominants:
        for dominant in instance.dominants:
            dom = g.instances[dominant]
            kills = instance.dominant2kills[dominant]
            updated_live = live.difference(kills)
            if dom.liveness:
                dom.liveness = dom.liveness.union(updated_live)
            else:
                dom.liveness = updated_live
        return set(), uses
    else:
        return live, uses


def analyze_fields_liveness(g, check):
    for instance in g.instances.values():
        if len(instance.input2ele) == 0:
            live, uses = analyze_fields_liveness_instance(g, instance.name, None)
            if check:
                assert len(live) == 0, "Fields %s of a pipeline state should not be live at the beginning." % live


def join_collect_killset(g, inst_name, target, inst2kill, scope):
    if inst_name == target:
        return set()
    elif inst_name in inst2kill:
        return inst2kill[inst_name]
    elif inst_name not in scope:
        return set()

    instance = g.instances[inst_name]

    if instance.element.output_fire == "all":
        kills = set()
        for next_name, next_port in instance.output2ele.values():
            ret = g.instances[next_name].element.defs
            ret = ret.union(join_collect_killset(g, next_name, target, inst2kill, scope))
            kills = kills.union(ret)
    elif instance.element.output_fire == "one":
        kills = set()
        first = True
        for next_name, next_port in instance.output2ele.values():
            ret = g.instances[next_name].element.defs
            ret = ret.union(join_collect_killset(g, next_name, target, inst2kill, scope))
            if first:
                kills = ret
                first = False
            else:
                kills = kills.intersect(ret)
    else:
        kills = set()

    inst2kill[inst_name] = kills
    return kills


def compute_join_killset(g):
    for instance in g.instances.values():
        if instance.dominants:
            for dominant in instance.dominants:
                kills = join_collect_killset(g, dominant, instance.name, {}, instance.passing_nodes + [dominant])
                instance.dominant2kills[dominant] = kills


def find_pipeline_state(g, instance):
    for start_name, state in g.pipeline_states:
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        if instance.name in subgraph:
            return state


def get_state_content(vars, pipeline_state, state_mapping, src2fields):
    content = " "
    for var in vars:
        fields = src2fields[var]
        current_type = pipeline_state
        for field in fields:
            if current_type[-1] == "*":
                current_type.rstrip('*').rstip()
            current_type = state_mapping[current_type][field]
        content += "%s %s; " % (current_type[0], fields[-1])
    return content


def get_entry_field(var, src2fields):
    fields = src2fields[var]
    return fields[-1]


def compile_smart_queue(g, q, src2fields):
    pipeline_state = find_pipeline_state(g, q.enq)
    enq_thread = g.get_thread_of(q.enq.name)
    deq_thread = g.get_thread_of(q.deq.name)

    if isinstance(q, queue_ast.QueueVariableSizeOne2Many):
        states, state_insts, elements, enq_alloc, enq_submit, deq_get, deq_release = \
            queue_ast.circular_queue_variablesize_one2many(q.name, q.size, q.n_cores)
    else:
        raise Exception("Smart queue: unimplemented for %s." % q)

    for state in states:
        g.addState(state)

    for state_inst in state_insts:
        g.newStateInstance(state_inst.state, state_inst.name, state_inst.init)

    src_cases = ""
    for i in range(q.n_cases):
        src_cases += "    case (type == %d): out%d(e);\n" % (i+1, i)
    classify_ele = Element(q.deq.name + "_classify",
                           [Port("in", ["q_entry*"])],
                           [Port("out" + str(i), ["q_entry*"]) for i in range(q.n_cases)],
                           r'''
        (q_entry* e) = in();
        uint16_t type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        output switch {
            %s
        }''' % (src_cases))

    elements.append(classify_ele)
    for element in elements:
        g.addElement(element)

    enq_submit_inst = enq_submit()
    deq_get_inst = deq_get()
    deq_release_inst = deq_release()
    classify_inst = ElementInstance(classify_ele.name, classify_ele.name + "_inst")

    new_instances = [enq_submit_inst, deq_get_inst, deq_release_inst, classify_inst]
    for inst in new_instances:
        g.newElementInstance(inst.element, inst.name, inst.args)

    # Connect deq_get -> classify
    g.connect(deq_get_inst.name, classify_inst.name)

    # Resource
    g.set_thread(enq_submit_inst.name, enq_thread)
    g.set_thread(deq_get_inst.name, deq_thread)
    g.set_thread(classify_inst.name, deq_thread)
    g.set_thread(deq_release_inst.name, deq_thread)  # TODO: deq_release

    # Memorize connections
    ins_map = []
    out_map = []

    for i in range(q.n_cases):
        ins = q.enq.input2ele["in" + str(i)]
        out = q.deq.output2ele["out" + str(i)]
        ins_map.append(ins)
        out_map.append(out)

    # Delete dummy dequeue and enqueue instances
    g.delete_instance(q.enq.name)
    g.delete_instance(q.deq.name)

    for i in range(q.n_cases):
        live = q.enq.liveness[i]
        uses = q.enq.uses[i]
        extras = uses.difference(live)

        ins = ins_map[i]
        out = out_map[i]

        # Create states
        state_entry = State("entry_" + q.name + str(i),
                            "uint16_t flags; uint16_t len; " +
                            get_state_content(live, pipeline_state, g.state_mapping, src2fields))
        state_pipeline = State("pipeline_" + q.name + str(i),
                               state_entry.name + "* entry; " +
                               get_state_content(extras, pipeline_state, g.state_mapping, src2fields))
        g.addState(state_entry)
        g.addState(state_pipeline)

        # Create elements
        # TODO: var-length field
        size_core_ele = Element(q.name + "_size_core" + str(i), [Port("in", [])], [Port("out", ["size_t", "size_t"])],
                                r'''output { out(sizeof(%s), state.core); }''' % state_entry.name)

        src = "%s* e = (%s*) in_entry();\n" % (state_entry.name, state_entry.name)
        for var in live:
            field = get_entry_field(var, src2fields)
            src += "e->%s = state.%s;\n" % (field, var)
        src += "e->flags |= %d << TYPE_SHIFT;\n" % (i+1)
        src += "output { out((q_entry*) e); }"
        fill_ele = Element(q.name + "_fill" + str(i),
                           [Port("in_entry", ["q_entry*"]), Port("in_pkt", [])],
                           [Port("out", ["q_entry*"])], src)
        fork = Element(q.name + "_fork" + str(i),
                       [Port("in", [])],
                       [Port("out_size_core", []), Port("out_fill", [])],
                       r'''output { out_size_core(); out_fill(); }''')
        save = Element(q.name + "_save" + str(i),
                       [Port("in", ["q_entry*"])],
                       [Port("out", [])],
                       r'''state.entry = (%s *) in(); output { out(); }''' % state_entry.name)
        g.addElement(size_core_ele)
        g.addElement(fill_ele)
        g.addElement(fork)
        g.addElement(save)

        # Create enq instances
        enq_alloc_inst = enq_alloc(q.name + "_enq_alloc" + str(i))
        size_core = ElementInstance(size_core_ele.name, size_core_ele.name + "_inst")
        fill_inst = ElementInstance(fill_ele.name, fill_ele.name + "_inst")
        fork_inst = ElementInstance(fork.name, fork.name + "_inst")
        new_instances = [enq_alloc_inst, size_core, fill_inst, fork_inst]
        for inst in new_instances:
            g.newElementInstance(inst.element, inst.name, inst.args)
            g.set_thread(inst.name, enq_thread)

        # Create deq instances
        save_inst = ElementInstance(save.name, save.name + "_inst")
        g.newElementInstance(save_inst.element, save_inst.name, save_inst.args)
        g.set_thread(save_inst.name, deq_thread)

        # Set pipeline state
        g.add_pipeline_state(save_inst.name, state_pipeline.name)
        save_inst = g.instances[save_inst.name]
        save_inst.liveness = live
        save_inst.extras = extras

        # Enqueue connection
        for in_inst, in_port in ins:
            g.connect(in_inst, fork_inst.name)
            g.connect(fork_inst.name, size_core.name, "out_size_core")
            g.connect(size_core.name, enq_alloc_inst.name)
            g.connect(enq_alloc_inst.name, fill_inst.name, "out", "in_entry")
            g.connect(fork_inst.name, fill_inst.name, "out_fill", "in_pkt")
            g.connect(fill_inst.name, enq_submit_inst.name)

        # Dequeue connection
        out_inst, out_port = out
        g.connect(classify_inst.name, save_inst.name, "out" + str(i))
        g.connect(save_inst.name, out_inst, "out", out_port)

        # Dequeue release connection
        node = get_node_before_release(out_inst, g, live)
        g.connect(node.name, deq_release_inst.name)


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
    order = []
    vis = set()
    for instance in g.instances.values():
        q = instance.element.special
        if q and q.enq == instance:
            order_smart_queues(q.enq.name, vis, order, g)

    for q in order:
        compile_smart_queue(g, q, src2fields)


def analyze_pipeline_states(g, check=True):
    # Annotate minimal join information
    annotate_join_info(g, False)
    src2fields = collect_defs_uses(g)
    compute_join_killset(g)
    analyze_fields_liveness(g, check)
    return src2fields


def compile_pipeline_states(g, check):
    if len(g.pipeline_states) == 0:
        # Never use per-packet states. No modification needed.
        return

    src2fields = analyze_pipeline_states(g, check)
    compile_smart_queues(g, src2fields)
    rename_references(g, src2fields)  # for state.entry
    insert_pipeline_states(g)