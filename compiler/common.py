import re

pipeline_include = r'''
typedef struct {
    int refcount;
} pipeline_state;

static inline void pipeline_unref(pipeline_state* s) {
    s->refcount--;
    if(s->refcount == 0) {
        free(s);
        //printf("free!\n");
    }
}

static inline void pipeline_ref(pipeline_state* s) {
    s->refcount++;
}
'''

standard_arg_format = "{0}_arg{1}"

def types_args_one_port(port, formatter):
    """
    Extract from a port:
    1. a list of "type arg"s
    2. a list of args

    :param port:
    :param formatter: a string formatter with {0} and/or {1} where {0} is the port name, and {2} is an arg ID.
    :return:
    """
    types_args = []
    args = []
    for i in range(len(port.argtypes)):
        arg = formatter.format(port.name, i)
        args.append(arg)
        types_args.append("%s %s" % (port.argtypes[i], arg))
    return types_args, args


def types_args_port_list(ports, formatter):
    """
    Extract from a list of ports:
    1. a list of types
    2. a list of args

    :param ports:
    :param formatter: a string formatter with {0} and/or {1} where {0} is the port name,
                      and {2} is an arg ID from of that particular port.
    :return:
    """
    args = []
    types = []
    for port in ports:
        for i in range(len(port.argtypes)):
            arg = formatter.format(port.name, i)
            args.append(arg)
        types += port.argtypes
    return types, args


def types_port_list(ports):
    types = []
    for port in ports:
        types += port.argtypes
    return types


def strip_all(s):
    new_s = s.lstrip().lstrip('\n').rstrip().rstrip('\n')
    if new_s == s:
        return s
    else:
        return strip_all(new_s)


def sanitize_type(t):
    if t is None:
        return t
    index = t.find('*')
    if index > 0:
        tokens = strip_all(t[:index]).split()
        return ' '.join(tokens) + '*'
    else:
        tokens = strip_all(t).split()
        return ' '.join(tokens)


def get_type_var(type_var):
    # type_var = strip_all(type_var)
    # index1 = type_var.rfind(' ')
    # index2 = type_var.rfind('*')
    # index = max(index1, index2)
    # return sanitize_type(type_var[:index + 1]), strip_all(type_var[index+1:])

    m = re.match('[ \n]*((struct[ ]+)?[a-zA-Z0-9_]+[ ]*[\*]*)[ ]*([a-zA-Z0-9_]+(\[[a-zA-Z_0-9]*\])*)', type_var)
    t = sanitize_type(m.group(1))
    var = m.group(3)
    m2 = re.match('[ ]*@shared\((.*)', type_var[m.end(3):])
    if m2:
        end = m2.group(1).rfind(')')
        pointer = m2.group(1)[:end]
        return t, var, "shared", pointer

    m2 = re.match('[ ]*@copysize\((.*)', type_var[m.end(3):])
    if m2:
        end = m2.group(1).rfind(')')
        pointer = m2.group(1)[:end]
        return t, var, "copysize", pointer

    return t, var, None, None


def get_type(type_var):
    return get_type_var(type_var)[0]


def get_var(type_var):
    return get_type_var(type_var)[1]

sizeof_dict = {
    "int": 4,
    "char": 4,
    "uint8_t": 1,
    "uint16_t": 2,
    "uint32_t": 4,
    "uint64_t": 8,
    "size_t": 8,
    "uintptr_t": 8,
    "struct ether_addr": 1, # array
    "struct ip_addr": 1, # array
    "struct eth_addr": 1, # array
}

class UnkownType(Exception):
    pass

def sizeof(t):
    if t[-1] == '*':
        return 8
    elif t in sizeof_dict:
        return sizeof_dict[t]
    else:
        raise UnkownType("Unknown type '%s'." % t)
