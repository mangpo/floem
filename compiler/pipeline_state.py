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


def compile_pipeline_states(g):
    if len(g.pipeline_states) == 0:
        # Never use per-packet states. No modification needed.
        return

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
