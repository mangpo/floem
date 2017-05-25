import queue_ast
from program import *
from pipeline_state_join import get_node_before_release
from join_handling import annotate_join_info


def allocate_pipeline_state(element, state):
    add = "  {0} *_state = ({0} *) malloc(sizeof({0}));\n".format(state)
    element.code = add + element.code


def insert_pipeline_state(element, state, start, instance, g):
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
                    if element.name == "_impl_prepare_get_response_release_version":
                        print element

    for port in element.outports:
        if len(port.argtypes) == 0:
            next_name, next_port = instance.output2ele[port.name]
            next_inst = g.instances[next_name]
            if len(next_inst.uses) > 0:
                port.argtypes.append(state + "*")
                if element.output_fire == "all":
                    element.output_code[port.name] = '%s(_state)' % port.name
                else:
                    for i in range(len(element.output_code)):
                        case, code = element.output_code[i]
                        m = re.search(port.name + '\(', code)
                        if m:
                            m2 = re.search(port.name + '\([ ]*\)', code)
                            assert m2, "Output port '%s' of element '%s' takes no argument, but it is called with argument(s): %s." \
                                       % (port.name, element.name, code)
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


def replace_recursive(code, var, new_var):
    m = re.search('[^a-zA-Z_0-9]state\.(' + var + ')[^a-zA-Z_0-9]', code)
    if m:
        code = code[:m.start(1)] + new_var + code[m.end(1):]
        return replace_recursive(code, var, new_var)
    else:
        return code


def replace_var(element, var, src2fields, prefix):
    new_var = prefix + src2fields[var][-1]
    if var == new_var:
        return
    element.code = replace_recursive(element.code, var, new_var)

    if element.output_fire == "all":
        for port in element.output_code:
            code = element.output_code[port]
            element.output_code[port] = replace_recursive(code, var, new_var)
    else:
        for i in range(len(element.output_code)):
            case, out_code = element.output_code[i]
            case = case.replace(var, new_var)
            out_code = replace_recursive(out_code, var, new_var)
            element.output_code[i] = (case, out_code)


def replace_states(element, live, extras, special_fields, src2fields):
    for var in live:
        if var not in special_fields:
            replace_var(element, var, src2fields, "entry->")

    for var in extras:
        replace_var(element, var, src2fields, "")

    for var in special_fields:
        replace_var(element, var, src2fields, "")

    if element.name.find("filter_full") >= 0:
        print element


def rename_entry_references(g, src2fields):
    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    for start_name in g.pipeline_states:
        instance = g.instances[start_name]
        # if instance.extras is not None:
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        for inst_name in subgraph:
            child = g.instances[inst_name]
            element = child.element
            if need_replacement(element, instance.liveness, instance.extras):
                if len(ele2inst[element.name]) == 1:
                    replace_states(element, instance.liveness, instance.extras, instance.special_fields, src2fields)
                else:
                    new_element = element.clone(inst_name + "_with_state_at_" + instance.name)
                    replace_states(new_element, instance.liveness, instance.extras, instance.special_fields, src2fields)
                    g.addElement(new_element)
                    child.element = new_element


def code_change(instance):
    return len(instance.uses) > 0
    # if len(instance.uses) == 0:
    #     return False
    #
    # for port in instance.element.inports:
    #     if len(port.argtypes) == 0:
    #         return True
    #
    # for port in instance.element.outports:
    #     if len(port.argtypes) == 0:
    #         return True
    #
    # return False


def duplicate_instances(g):
    parents = {}
    for instance in g.instances.values():
        parents[instance.name] = []

    for start_name in g.pipeline_states:
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        for inst_name in subgraph:
            parents[inst_name].append(start_name)

    duplicate = False
    for inst_name in parents:
        myparents = parents[inst_name]
        instance = g.instances[inst_name]

        if len(myparents) > 1 and code_change(instance):
            duplicate = True
            break

    if duplicate:
        raise Exception("Unimplemented.")


def insert_pipeline_states(g):
    duplicate_instances(g)

    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    for start_name in g.pipeline_states:
        state = g.pipeline_states[start_name]
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
            ele2inst[new_element.name] = [instance]

        # Pass state pointers
        vis = set()
        for inst_name in subgraph:
            child = g.instances[inst_name]
            element = child.element
            # If multiple instances can share the same element, make sure we don't modify an element more than once.
            if element.name not in vis and code_change(child):
                vis.add(element.name)
                if len(ele2inst[element.name]) == 1:
                    # TODO: modify element: empty port -> send state*
                    insert_pipeline_state(element, state, inst_name == start_name, child, g)
                else:
                    # TODO: create new element: empty port -> send state*
                    new_element = element.clone(inst_name + "_with_state")
                    vis.add(new_element.name)
                    insert_pipeline_state(new_element, state, inst_name == start_name, child, g)
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
        if code[m.start()+1] is not '=':  # not a comparison
            use = False
    else:
        m2 = re.match('(\[[^\]]+\])*[ ]*=[^=]', code[m.start():])  # TODO: nested array
        if m2:
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


def kill_live(live, defs):
    ret = set()
    for var in live:
        include = True
        for d in defs:
            m = re.match(d, var)
            if m:
                include = False
                break
        if include:
            ret.add(var)
    return ret


def analyze_fields_liveness_instance(g, name, in_port):
    instance = g.instances[name]

    # Smart queue
    q = instance.element.special
    if q and q.enq == instance:
        no = int(in_port[2:])
        if instance.liveness:
            return instance.liveness[no], instance.uses[no]

        instance.liveness = {}
        instance.uses = {}
        deq = q.deq
        deq.liveness = {}
        deq.uses = {}
        for i in range(q.n_cases):
            out_port = "out" + str(i)
            next_name, next_port = deq.output2ele[out_port]
            ret_live, ret_uses = analyze_fields_liveness_instance(g, next_name, next_port)
            deq.liveness[i] = ret_live
            deq.uses[i] = ret_uses
            instance.liveness[i] = ret_live.union(instance.element.uses)
            instance.uses[i] = ret_live.union(instance.element.uses)

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
    live = kill_live(live, instance.element.defs) # live.difference(instance.element.defs)
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


def analyze_fields_liveness(g):
    for instance in g.instances.values():
        q = instance.element.special
        if len(instance.input2ele) == 0:
            live, uses = analyze_fields_liveness_instance(g, instance.name, None)


def check_pipeline_state_liveness(g):
    for instance in g.instances.values():
        if len(instance.input2ele) == 0 and instance.liveness:
            assert len(instance.liveness) == 0, \
                ("Fields %s of a pipeline state should not be live at the beginning at element instance '%s'." %
                 (instance.liveness, instance.name))


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
    for start_name in g.pipeline_states:
        state = g.pipeline_states[start_name]
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        if instance.name in subgraph:
            return state


def get_entry_content(vars, pipeline_state, state_mapping, src2fields):
    content = " "
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
                mapping = state_mapping[current_type]
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


def get_state_content(vars, pipeline_state, state_mapping, src2fields, special):
    content = " "
    for var in vars:
        fields = src2fields[var]
        current_type = pipeline_state
        for field in fields:
            if current_type[-1] == "*":
                current_type.rstrip('*').rstip()
            current_type = state_mapping[current_type][field]
        content += "%s %s; " % (current_type[0], fields[-1])

    for var in special:
        t, name, special_t, info = special[var]
        content += "%s %s; " % (t, name)
    return content


def get_entry_field(var, src2fields):
    fields = src2fields[var]
    return fields[-1]


def compile_smart_queue(g, q, src2fields):
    pipeline_state = find_pipeline_state(g, q.enq)
    enq_thread = g.get_thread_of(q.enq.name)
    deq_thread = g.get_thread_of(q.deq.name)

    if re.match("_impl", q.enq.name):
        prefix = "_impl_"
    elif re.match("_spec", q.enq.name):
        prefix = "_spec_"
    else:
        prefix = ""

    if isinstance(q, queue_ast.QueueVariableSizeOne2Many):
        states, state_insts, elements, enq_alloc, enq_submit, deq_get, deq_release = \
            queue_ast.circular_queue_variablesize_one2many(q.name, q.size, q.n_cores)
        scan = None
    elif isinstance(q, queue_ast.QueueVariableSizeMany2One):
        states, state_insts, elements, enq_alloc, enq_submit, deq_get, deq_release, scan = \
            queue_ast.circular_queue_variablesize_many2one(q.name, q.size, q.n_cores, q.scan_type)
        scan_thread = g.get_thread_of(q.scan.name)
    else:
        raise Exception("Smart queue: unimplemented for %s." % q)

    for state in states:
        g.addState(state)

    for state_inst in state_insts:
        g.newStateInstance(state_inst.state, state_inst.name, state_inst.init)

    if isinstance(q, queue_ast.QueueVariableSizeOne2Many):
        deq_types = ["q_entry*", "size_t"]
        deq_src_in = "(q_entry* e, size_t core) = in();"
        deq_args_out = "e,core"
    elif isinstance(q, queue_ast.QueueVariableSizeMany2One):
        deq_types = ["q_entry*"]
        deq_src_in = "(q_entry* e) = in();"
        deq_args_out = "e"

    src_cases = ""
    for i in range(q.n_cases):
        src_cases += "    case (type == %d): out%d(%s);\n" % (i + 1, i, deq_args_out)
    src_release = "    case (type == 0): release(e);\n"
    classify_ele = Element(q.deq.name + "_classify",
                           [Port("in", deq_types)],
                           [Port("out" + str(i), deq_types) for i in range(q.n_cases)]
                           + [Port("release", ["q_entry*"])],
                           r'''
        %s
        int type = -1;
        if (e != NULL) type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        output switch {
            %s
        }''' % (deq_src_in, src_cases + src_release))

    scan_classify_ele = Element(q.deq.name + "_scan_classify",
                           [Port("in", deq_types)],
                           [Port("out" + str(i), deq_types) for i in range(q.n_cases)],
                           r'''
        %s
        uint16_t type = 0;
        if (e != NULL) type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        output switch {
            %s
        }''' % (deq_src_in, src_cases))

    elements.append(classify_ele)
    for element in elements:
        g.addElement(element)

    deq_get_inst = deq_get(q.deq.name + "_get")
    deq_release_inst = deq_release(q.deq.name + "_release")
    classify_inst = ElementInstance(classify_ele.name, classify_ele.name + "_inst")
    new_instances = [deq_get_inst, deq_release_inst, classify_inst]

    if scan:
        g.addElement(scan_classify_ele)
        scan_inst = scan(q.enq.name + "_scan")
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
        ins = q.enq.input2ele["in" + str(i)]
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

        if isinstance(q, queue_ast.QueueVariableSizeOne2Many) and 'core' in live:
            live = live.difference(set(['core']))
            extras.add('core')

        ins = ins_map[i]
        out = out_map[i]

        # Create states
        content, special = get_entry_content(live, pipeline_state, g.state_mapping, src2fields)
        state_entry = State("entry_" + q.name + str(i),
                            "uint16_t flags; uint16_t len; " + content)
        state_pipeline = State("pipeline_" + q.name + str(i),
                               state_entry.name + "* entry; " +
                               get_state_content(extras, pipeline_state, g.state_mapping, src2fields, special))
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
        fill_ele = Element(q.name + "_fill" + str(i),
                           [Port("in_entry", ["q_entry*"]), Port("in_pkt", [])],
                           [Port("out", ["q_entry*"])], fill_src)  # TODO
        fork = Element(q.name + "_fork" + str(i),
                       [Port("in", [])],
                       [Port("out_size_core", []), Port("out_fill", [])],
                       r'''output { out_size_core(); out_fill(); }''')

        save_src = deq_src_in
        if isinstance(q, queue_ast.QueueVariableSizeOne2Many) and 'core' in live:
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
            enq_alloc_inst = enq_alloc(prefix + q.name + "_enq_alloc" + str(i) + "_from_" + in_inst)
            enq_submit_inst = enq_submit(prefix + q.name + "_enq_submit" + str(i) + "_from_" + in_inst)
            size_core = ElementInstance(size_core_ele.name, prefix + size_core_ele.name + "_from_" + in_inst)
            fill_inst = ElementInstance(fill_ele.name, prefix + fill_ele.name + "_from_" + in_inst)
            fork_inst = ElementInstance(fork.name, prefix + fork.name + "_from_" + in_inst)
            new_instances = [enq_alloc_inst, size_core, fill_inst, fork_inst]
            for inst in new_instances:
                g.newElementInstance(inst.element, inst.name, inst.args)
                g.set_thread(inst.name, in_thread)
                instance = g.instances[inst.name]
                instance.liveness = live
                instance.uses = uses

            g.newElementInstance(enq_submit_inst.element, enq_submit_inst.name, enq_submit_inst.args)
            g.set_thread(enq_submit_inst.name, in_thread)
            instance = g.instances[enq_submit_inst.name]
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
    order = []
    vis = set()
    for instance in g.instances.values():
        q = instance.element.special
        if q and q.enq == instance:
            order_smart_queues(q.enq.name, vis, order, g)

    for q in order:
        compile_smart_queue(g, q, src2fields)


def analyze_pipeline_states(g):
    # Annotate minimal join information
    g.print_graphviz()
    annotate_join_info(g, False)
    src2fields = collect_defs_uses(g)
    compute_join_killset(g)
    analyze_fields_liveness(g)
    return src2fields


def compile_pipeline_states(g):
    if len(g.pipeline_states) == 0:
        # Never use per-packet states. No modification needed.
        return

    src2fields = analyze_pipeline_states(g)
    compile_smart_queues(g, src2fields)
    print "------------------------------------------"
    g.print_graphviz()
    rename_entry_references(g, src2fields)  # for state.entry
    insert_pipeline_states(g)