import re
import copy


class LivenessInfo:
    def __init__(self, instance, port, n_ports, version, killed):
        self.instance = instance
        self.port = port
        self.n_ports = n_ports
        self.version = version
        self.killed = killed

    def __copy__(self):
        return LivenessInfo(self.instance, self.port, self.n_ports, self.version, self.killed)


class LivenessCollection:
    def __init__(self):
        self.var2info = {}  # map var to (instance, port, n_ports, version, use/kill)

    def add_liveness_collection(self, other, collapse):
        if len(self.var2info) == 0:
            self.var2info = copy.deepcopy(other.var2info)
        else:
            for var in other.var2info:
                if var in self.var2info:
                    self.var2info[var] = self.var2info[var] + other.var2info[var]
                else:
                    self.var2info[var] = copy.copy(other.var2info[var])

                if collapse:
                    self.var2info[var] = self.collapse_liveness(self.var2info[var])

    def kill_var(self, var):
        if var in self.var2info:
            liveness_list = self.var2info[var]
            for liveness in liveness_list:
                liveness.killed = True

            self.var2info[var] = self.collapse_liveness(liveness_list)


    def add_var(self, var, instance, port, n_ports, version):
        liveness = LivenessInfo(instance, port, n_ports, version, False)
        if var not in self.var2info:
            self.var2info[var] = []
        self.var2info[var].append(liveness)


    def collapse_liveness(self, liveness_list):
        inst2info = {}
        for liveness in liveness_list:
            instance = liveness.instance
            if instance not in inst2info:
                inst2info[instance] = []
            inst2info[instance].append(liveness)

        for instance in inst2info:
            inst_liveness_list = inst2info[instance]
            n_ports = inst_liveness_list[0].n_ports

            port2info = {}
            for liveness in inst_liveness_list:
                port = liveness.port
                if port not in port2info:
                    port2info[port] = []
                port2info[port].append(liveness)

            # Have all ports, try to collapse
            if len(port2info) == n_ports:
                can_remove = False
                for port in port2info:
                    all_killed = True
                    port_liveness_list = port2info[port]
                    for liveness in port_liveness_list:
                        all_killed = all_killed and liveness.killed
                        if not all_killed:
                            break

                    if all_killed:
                        can_remove = True
                        break

                if can_remove:
                    # Remove instance
                    liveness_list = [x for x in liveness_list if x.instance is not instance]
                else:
                    # For each port, keep just one version
                    add_list = []
                    for port in port2info:
                        port_liveness_list = port2info[port]
                        liveness = port_liveness_list[0]
                        new_liveness = liveness.copy()
                        new_liveness.killed = False
                        add_list.append(new_liveness)
                    liveness_list = [x for x in liveness_list if x.instance is not instance] + add_list

            return liveness_list


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
            code = code[m.start(0):]
            return src, fields, code

def find_next_def_use(code):
    m = re.search('[^a-zA-Z0-9_]state\.', code)
    if not m:
        return None, None, None, None

    src, fields, code = find_all_fields(code)

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


def analyze_fields_liveness(g):
    vis = []
    ready = []

    for instance in g.instances.values():
        instance.liveness = LivenessCollection()
        output_instances = []
        for insts in instance.output2ele.values():
            output_instances + insts
        instance.output_instances = set(output_instances)

        if len(instance.output2ele) == 0:
            ready.append(instance)

    while len(ready) > 0:
        working = ready.pop()
        vis.append(working)
        for def_var in working.element.defs:
            working.liveness.kill_var(def_var)

        port_id = 0
        n_ports = len(working.input2ele)
        for port in working.input2ele:
            insts = working.input2ele[port]
            version = 0
            for inst_name in insts:
                inst = g.instances[inst_name]
                inst.vis_output_instances.add(working.name)
                inst.liveness.add_liveness_collection(working.liveness)
                for use_var in working.element.uses:
                    inst.liveness.add_var(use_var, working.name, port_id, n_ports, version)

                assert (inst not in vis), "Instance %s is already been visited." % inst.name
                ready.append(inst)
                version += 1
            port_id += 1


def compile_pipeline_states(g):
    if len(g.pipeline_states) == 0:
        # Never use per-packet states. No modification needed.
        return

    src2fields = collect_defs_uses(g)
    analyze_fields_liveness(g)
    compile_smart_queues(g)
    insert_pipeline_states(g)
