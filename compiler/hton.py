import target, common


def get_all_types_fields(g, state_name, prefix):
    if state_name in g.states:
        state = g.states[state_name]
        ret = []
        for field in state.fields:
            if field in state.mapping:
                t = state.mapping[field][0]
                ret += get_all_types_fields(g, t, prefix + field + '.')
        return ret
    else:
        return [(state_name, prefix[:-1])]

htons = "htons"
htonl = "htonl"
htonp = "htonp"
size2convert = {1: "", 2: htons, 4: htonl, 8: htonp}
def hton_instance(g, instance, state_name):
    src = "  (size_t size, void* pkt, void* buf) = inp();\n"
    src += "  {0}* p = ({0}*) pkt;\n".format(state_name)
    types_fields = get_all_types_fields(g, state_name, 'p->')
    for type, field in types_fields:
        try:
            size = common.sizeof(type)
            if size == 2 or size == 4 or size == 8:
                src += "  {0} = {1}({0});\n".format(field, size2convert[size])
        except:
            pass
    element = instance.element
    new_element = element.clone(element.name + "_" + state_name)
    new_element.code = src
    instance.element = new_element


def is_on_CPU(g, instance):
    t = instance.thread
    d = (t in g.thread2device) and g.thread2device[t][0]
    return d == target.CPU or d == False


def hton_pass(g):
    for inst in g.instances.values():
        special = inst.element.special
        if isinstance(special, tuple) and special[0] == 'hton':
            if is_on_CPU(g, inst):
                hton_instance(g, inst, special[1])
