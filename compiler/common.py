primitive_types = ["int", "long", "float", "double"] # TODO
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