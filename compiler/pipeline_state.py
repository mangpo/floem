from program import *
from join_handling import annotate_join_info, clean_minimal_join_info
from smart_queue_compile import compile_smart_queues
import codegen, graph_ir


def allocate_pipeline_state(g, element, state):
    assert not element.output_fire == "multi", "Batch element '%s' cannot allocate pipeline state." % element.name
    state_obj = g.states[state]
    add = "  {0} *_state = ({0} *) malloc(sizeof({0}));\n".format(state)
    add += "  _state->refcount = 1;\n"
    init = codegen.init_pointer(state_obj, state_obj.init, '_state')
    element.prepend_code(add + init)
    element.cleanup = "  pipeline_unref((pipeline_state*) _state);\n"


def insert_reference_count(st_name, g):
    for st_inst in g.state_instances.values():
        assert not st_inst.state.name == st_name, \
            ("Pipeline state type '%s' shouldn't be used as the type of non-pipeline state '%s'." %
             (st_name, st_inst.name))

    state = g.states[st_name]
    state.content = "int refcount; " + state.content


def insert_pipeline_at_port(instance, best_port, g, state):
    l = []
    for prev_name, prev_port in instance.input2ele[best_port]:
        prev = g.instances[prev_name]
        prev_element = prev.element

        port = [port for port in prev_element.outports if port.name == prev_port][0]
        port.argtypes.append(state + "*")
        prev_element.add_output_value(port.name, '_state')

    element = instance.element
    port = [port for port in element.inports if port.name == best_port][0]
    element_insert_arg_at_port(element, port, state)
    port.argtypes.append(state + "*")


def code_insert_arg_at_port(src, port, state):
    argtypes = port.argtypes
    m = re.search('[^a-zA-Z0-9_](' + port.name + '[ ]*\(([^\)]*)\))', src)
    if m is None:
        m = re.search('(' + port + '[ ]*\(([^\)]*)\))', src)

    if m is None:
        pass

    p = m.start(1)
    codegen.check_no_args(m.group(2))
    c1, p1 = codegen.last_non_space(src, p)
    c2, p2 = codegen.first_non_space(src, m.end(1))
    c0, p0 = codegen.last_non_space(src, p1 - 1)

    if c0 == ')' and c1 == '=' and c2 == ';':
        #src = remove_asgn_stmt(funcname, src, port2args, port, p1, p2 + 1, argtypes)
        src = src[:p0] + ', {0}* _state'.format(state) + src[p0:]
    elif (c1 == ';' or c1 is None) and c2 == ';':
        #src = remove_nonasgn_stmt(funcname, src, port2args, port, p1 + 1, p2 + 1, argtypes)
        add = "\n("
        for i in range(len(argtypes)):
            type = argtypes[i]
            add += "{0} _dummy{1}, ".format(type, i)
        add += '{0}* _state) = {1}()'.format(state, port.name)
        if p1 is None:
            p1 = -1
        src = src[:p1+1] + add + src[p2:]
    else:
        #src = remove_expr(funcname, src, port2args, port, p, m.end(1), argtypes)
        src = src[:p] + "_dummy" + src[m.end(1):]
        src = "({0} _dummy, {1}* _state) = {2}();\n".format(argtypes[0], state, port.name) + src

    return src


def element_insert_arg_at_port(element, port, state):
    element.code = code_insert_arg_at_port(element.code, port, state)
    if element.code_cavium:
        element.code_cavium = code_insert_arg_at_port(element.code_cavium, port, state)

def code_insert_arg_at_empyt_port(src, port, state):
    m = re.search('[^a-zA-Z0-9_](' + port.name + ')\(', src)
    if m:
        add = '%s *_state = ' % state
        src = src[:m.start(1)] + add + src[m.start(1):]
    else:
        add = '  %s *_state = %s();\n' % (state, port.name)
        src = add + src
    return src


def element_insert_arg_at_empyt_port(element, port, state):
    element.code = code_insert_arg_at_empyt_port(element.code, port, state)
    if element.code_cavium:
        element.code_cavium = code_insert_arg_at_empyt_port(element.code_cavium, port, state)


def insert_pipeline_state(instance, state, start, g):
    element = instance.element
    assert not element.output_fire == "multi", "Cannot insert pipeline state for batch element '%s'." % element.name
    no_state = True
    if not start:
        inserted = False
        for port in element.inports:
            if len(port.argtypes) == 0:
                inserted = True
                port.pipeline = True
                port.argtypes.append(state + "*")
                if no_state:
                    element_insert_arg_at_empyt_port(element, port, state)
                    no_state = False

        if not inserted:
            best_port = None
            n_insts = 1000
            for port in element.inports:
                if port.name in instance.input2ele:
                    l = instance.input2ele[port.name]
                    all = True
                    for prev_name, prev_port in l:
                        prev = g.instances[prev_name]
                        if len(prev.uses) == 0 or not prev.element.output_fire == "all":
                            all = False
                            break
                    if all and len(l) < n_insts:
                        n_insts = len(l)
                        best_port = port.name

            if best_port:
                insert_pipeline_at_port(instance, best_port, g, state)
            else:
                raise Exception("No easy way to insert pipeline state for instance '%s'." % instance.name)

    for port in element.outports:
        if len(port.argtypes) == 0:
            next_name, next_port = instance.output2ele[port.name]
            next_inst = g.instances[next_name]
            if len(next_inst.uses) > 0:
                port.pipeline = True
                port.argtypes.append(state + "*")
                element.reassign_output_values(port.name, "_state")

    element.replace_in_code('[^a-zA-Z_0-9](state.)', '_state->')


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
        elif element.output_fire == "multi":
            pass
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
    if var == new_var:
        return
    element.replace_in_code('[^a-zA-Z_0-9]state\.(' + var + ')[^a-zA-Z_0-9]', new_var)


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
                    child.element = new_element
                    replace_states(new_element, instance.liveness, instance.extras, instance.special_fields, src2fields)
                    g.addElement(new_element)


def code_change(instance):
    return len(instance.uses) > 0

dup_id = 0

def duplicate_subgraph(g, start_name, parents):
    global  dup_id
    suffix = "_dup" + str(dup_id)
    dup_id += 1

    dup_set = set()

    # Duplicate element instances
    for inst_name in parents:
        myparents = parents[inst_name]
        instance = g.instances[inst_name]
        if len(myparents) > 1 and code_change(instance) and start_name in myparents:
            dup_set.add(inst_name)
            g.copy_node_and_element(inst_name, suffix)

    # Duplicate connections
    for inst_name in dup_set:
        instance = g.instances[inst_name]
        for inport in instance.input2ele:
            for prev_name, prev_port in instance.input2ele[inport]:
                theirs = parents[prev_name]
                if len(theirs) == 1:
                    g.disconnect(prev_name, inst_name, prev_port, inport)
                    g.connect(prev_name, inst_name + suffix, prev_port, inport)
                elif len(theirs) > 1:
                    g.connect(prev_name + suffix, inst_name + suffix, prev_port, inport)
                else:
                    raise Exception("This shouldn't happen. Cannot duplicate an edge when its incoming node doesn't have pipeline state.")

        for outport in instance.output2ele:
            next_name, next_port = instance.output2ele[outport]
            theirs = parents[next_name]
            if next_name not in dup_set:
                g.connect(inst_name + suffix, next_name, outport, next_port)

    # Delete start_name from parents
    for inst_name in dup_set:
        myparents = parents[inst_name]
        myparents.remove(start_name)


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

    if duplicate:
        for start_name in g.pipeline_states:
            duplicate_subgraph(g, start_name, parents)


def insert_pipeline_states(g):
    duplicate_instances(g)

    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    vis_states = []
    for start_name in g.pipeline_states:
        state = g.pipeline_states[start_name]
        subgraph = set()
        g.find_subgraph(start_name, subgraph)

        # Insert refcount field
        if state not in vis_states:
            insert_reference_count(state, g)
            vis_states.append(state)

        # Allocate state
        instance = g.instances[start_name]
        element = instance.element

        if len(ele2inst[element.name]) == 1:
            allocate_pipeline_state(g, element, state)
        else:
            new_element = element.clone(start_name + "_with_state_alloc")
            allocate_pipeline_state(g, new_element, state)
            g.addElement(new_element)
            instance.element = new_element
            ele2inst[new_element.name] = [instance]

        # Pass state pointers
        vis = set()
        for inst_name in subgraph:
            child = g.instances[inst_name]
            element = child.element
            # If multiple instances can share the same element, make sure we don't modify an element more than once.
            if child.name not in vis and code_change(child):
                vis.add(child.name)
                if len(ele2inst[element.name]) == 1:
                    # TODO: modify element: empty port -> send state*
                    insert_pipeline_state(child, state, inst_name == start_name, g)
                else:
                    # TODO: create new element: empty port -> send state*
                    new_element = element.clone(inst_name + "_with_state")
                    child.element = new_element
                    insert_pipeline_state(child, state, inst_name == start_name, g)
                    g.addElement(new_element)
                    vis.add(new_element.name)


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
            m = re.match(d + '$', var)
            if m: include = False; break
            m = re.match(d + '\.', var)
            if m: include = False; break
            m = re.match(d + '->', var)
            if m: include = False; break
        if include:
            ret.add(var)
    return ret


def analyze_fields_liveness_instance(g, name, in_port):
    instance = g.instances[name]

    # Smart queue
    q = instance.element.special
    if isinstance(q, graph_ir.Queue) and q.enq == instance:
        no = int(in_port[3:])
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
    elif q and q.deq == instance:
        return set(), set()

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
        if len(instance.input2ele) == 0:
            live, uses = analyze_fields_liveness_instance(g, instance.name, None)


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


def analyze_pipeline_states(g):
    # Annotate minimal join information
    annotate_join_info(g, False)
    src2fields = collect_defs_uses(g)
    compute_join_killset(g)
    analyze_fields_liveness(g)
    return src2fields


def find_starting(g, name):
    instance = g.instances[name]
    if instance.element.output_fire == "multi":
        ret = set()
        for next_name, next_port in instance.output2ele.values():
            mine = find_starting(g, next_name)
            ret = ret.union(mine)
        return ret
    else:
        return set([name])


def is_valid_start(g, name):
    """
    Not valid if it rearch dequeue or scan before enqueue
    """
    instance = g.instances[name]

    if isinstance(instance.element.special, graph_ir.Queue):
        if instance.element.special.enq == instance:
            return True
        else:
            return False

    ret = True
    for next, port in instance.output2ele.values():
        ret = ret and is_valid_start(g, next)
    return ret


def insert_starting_point(g, pktstate):
    inserted = False

    roots = g.find_roots()
    for root in roots:
        if not isinstance(g.instances[root].element.special, graph_ir.Queue):
            starts = find_starting(g, root)

            for start in starts:
                if is_valid_start(g, start):
                    g.pipeline_states[start] = pktstate.__class__.__name__
                    inserted = True


    # for instance in g.instances.values():
    #     if instance.element.special:
    #         continue
    #
    #     candidate = False
    #     for port in instance.element.outports:
    #         if len(port.argtypes) == 0:
    #             candidate = True
    #             break
    #
    #     if not candidate:
    #         continue
    #
    #     for port in instance.element.inports:
    #         if len(port.argtypes) == 0:
    #             if port.name in instance.input2ele:
    #                 candidate = False
    #                 break
    #
    #     if not candidate:
    #         continue
    #
    #     g.pipeline_states[instance.name] = pktstate.__class__.__name__
    #     inserted = True

    if not inserted:
        raise Exception("Cannot find an entry point to create per-packet state '%s'." % pktstate.__class__.__name__)


def compile_pipeline_states(g, pktstate):
    if len(g.pipeline_states) == 0 and pktstate is None:
        # Never use per-packet states. No modification needed.
        return

    if pktstate:
        insert_starting_point(g, pktstate)

    graphviz = False

    if graphviz:
        g.print_graphviz()

    src2fields = analyze_pipeline_states(g)
    compile_smart_queues(g, src2fields)

    if graphviz:
        print "-------------------- insert smart queue ----------------------"
        g.print_graphviz()

    rename_entry_references(g, src2fields)  # for state.entry
    insert_pipeline_states(g)

    if graphviz:
        print "-------------------- insert pipeline state ----------------------"
        g.print_graphviz()


def pipeline_state_pass(g, pktstate=None):
    compile_pipeline_states(g, pktstate)
    clean_minimal_join_info(g)