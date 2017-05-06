import re


def allocate_pipeline_state(element, state):
    add = '  {0} *_state = ({0} *) malloc(sizeof({0}));\n'.format(state)
    element.code = add + element.code


def insert_pipeline_state(element, state):
    no_state = True
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
            element.output_code[port.name] = '%s(_state)' % port.name

    element.code = element.code.replace('state.', '_state->')


def insert_pipeline_states(g):
    ele2inst = {}
    for instance in g.instances.values():
        if instance.element.name not in ele2inst:
            ele2inst[instance.element.name] = []
        ele2inst[instance.element.name].append(instance)

    for instance, state in g.pipeline_states:
        subgraph = set()
        g.find_subgraph(instance, subgraph)

        # Allocate state
        element = g.instances[instance].element
        allocate_pipeline_state(element, state)

        # Pass state pointers
        for inst_name in subgraph:
            inst = g.instances[inst_name]
            element = inst.element
            if len(ele2inst[element.name]) == 1:
                # TODO: modify element: empty port -> send state*
                insert_pipeline_state(element, state)
            else:
                # TODO: create new element: empty port -> send state*
                new_element = element.clone(element.name + "_with_state")
                insert_pipeline_state(new_element, state)
                g.addElement(new_element)
                instance.element = new_element


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


def analyze_fields_liveness_instance(g, name):
    instance = g.instances[name]
    if instance.liveness:
        # visited
        if instance.dominants:
            return set()
        else:
            return instance.liveness

    # Union its children
    if instance.liveness:
        live = instance.liveness
    else:
        live = set()
    for next_name, next_port in instance.output2ele.values():
        ret = analyze_fields_liveness_instance(g, next_name)
        live = live.union(ret)

    # - kills + uses
    live = live.difference(instance.element.defs)
    live = live.union(instance.element.uses)
    instance.liveness = live

    if instance.dominants:
        for dominant in instance.dominants:
            dom = g.instances[dominant]
            kills = instance.dominant2kills[dominant]
            updated_live = live.difference(kills)
            if dom.liveness:
                dom.liveness = dom.liveness.union(updated_live)
            else:
                dom.liveness = updated_live
        return set()
    else:
        return live


def analyze_fields_liveness(g):
    for instance in g.instances.values():
        if len(instance.input2ele) == 0:
            live = analyze_fields_liveness_instance(g, instance.name)
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
            ret = g.instances[next_name].kills.union(join_collect_killset(g, next_name, target, inst2kill))
            kills = kills.union(ret)
    elif instance.element.output_fire == "one":
        kills = set()
        first = True
        for next_name, next_port in instance.output2ele.values():
            ret = g.instances[next_name].kills.union(join_collect_killset(g, next_name, target, inst2kill))
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


def compile_pipeline_states(g):
    if len(g.pipeline_states) == 0:
        # Never use per-packet states. No modification needed.
        return

    src2fields = collect_defs_uses(g)
    compute_join_killset(g)
    analyze_fields_liveness(g)
    # TODO: compile_smart_queues(g)
    insert_pipeline_states(g)
