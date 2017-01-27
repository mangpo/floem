from ast import *
import re

var_id = 0
def fresh_var_name():
    global var_id
    name = '_x' + str(var_id)
    var_id += 1
    return name

def check_no_args(args):
    if not(args == ""):
        raise Exception("Cannot pass an argument when retrieving data from an input port.")

"""Return the last charactor before s[i] that is not a space, along with its index.
s -- string
i -- index
"""
def last_non_space(s,i):
    i -= 1
    while i >= 0 and s[i] == ' ':
        i -= 1

    if i >= 0:
        return (s[i],i)
    else:
        return (None,-1)

"""Return the first charactor start from s[i] that is not a space, along with its index.

s -- string
i -- index
"""
def first_non_space(s,i):
    l = len(s)
    while i < l and s[i] == ' ':
        i += 1

    if i < l:
        return (s[i],i)
    else:
        return (None,-1)

"""Remove the reading from port statment from src, 
and put its LHS of the statement in port2args.

src       -- string source code
port2args -- map port name to a list of (type,argument name)
port      -- port name
p_eq      -- position of '=' of the statement to be removed
p_end     -- the ending positiion of the statement to be removed (after ';')
inport_types -- data types of the port
"""
def remove_asgn_stmt(src,port2args,port,p_eq, p_end, inport_types):
    p_start = max(0,src[:p_eq].rfind(';'))
    if src[p_start] == ';':
        p_start += 1

    decl = src[p_start:p_eq].lstrip().rstrip().lstrip("(").rstrip(")").lstrip().rstrip()
    args = decl.split(",")
    port2args[port] = args
    argtypes = [x.split()[0] for x in args]

    if not(argtypes == inport_types):
        raise Exception("Argument types mismatch at an input port '%s'." % port)
        
    return src[:p_start] + src[p_end:]

"""Remove the reading from port statment from src, 
when the reading is not saved in any variable or used in any expression.

src       -- string source code
port2args -- map port name to a list of (type,argument name)
port      -- port name
p_start   -- the starting position of the statement to be removed
             (after previous ';' or 0 if no previous ';')
p_end     -- the ending positiion of the statement to be removed (after ';')
inport_types -- data types of the port
"""
def remove_nonasgn_stmt(src,port2args,port,p_start, p_end, inport_types):
    args = [t + ' ' + fresh_var_name() for t in inport_types]
    port2args[port] = args
    return src[:p_start] + src[p_end:]
    
"""Remove the reading from port expression from src, 
and replace it with a fresh variable name.

src       -- string source code
port2args -- map port name to a list of (type,argument name)
port      -- port name
p_start   -- the starting position of the expression to be removed
p_end     -- the ending positiion of the statement to be removed (after ')')
inport_types -- data types of the port
"""
def remove_expr(src,port2args,port,p_start, p_end, inport_types):
    n = len(inport_types)
    if n > 1 or n == 0:
        raise Exception("Input port '%s' returns %d values. It cannot be used as an expression." % (port,n))

    name = fresh_var_name()
    port2args[port] = [inport_types[0] + ' ' + name]
    return src[:p_start] + name + src[p_end:]


def element_to_function(src, funcname, inports, output2func, local_state, state_rename):
    """Turn an element into a function.
    - Read from an input port => input argument(s).
    - Write to an output port => a function call.

    :param src: string of element source code
    :param funcname: string of function name
    :param inports: a list of Port
    :param output2func: dictionary of an output port name to (function name, port)
    :param local_state: a state object local for this element
    :param state_rename: a map from old state name to new state name
    :return: a string of function source code
    """
    src = ' ' + src
    # A dictionary to collect function arguments.
    port2args = {}
    # Collect arguments and remove input ports from src.
    for portinfo in inports:
        port = portinfo.name
        argtypes = portinfo.argtypes
        match = False
        index = 0
        while not(match):
            m = re.search(port + '[ ]*\(([^\)]*)\)',src[index:])
            if m == None:
                raise Exception("Element '%s' never get data from input port '%s'." % (funcname,port))
            p = m.start(0)
            if p == 0 or re.search('[^a-zA-Z0-9_]',src[p-1]):
                check_no_args(m.group(1))
                c1, p1 = last_non_space(src,p)
                c2, p2 = first_non_space(src,m.end(0))
                c0, p0 = last_non_space(src,p1-1)

                if c0 == ')' and c1 == '=' and c2 == ';':
                    src = remove_asgn_stmt(src,port2args,port,p1,p2+1,argtypes)
                elif (c1 == ';' or c1 is None) and c2 == ';':
                    src = remove_nonasgn_stmt(src,port2args,port,p1+1,p2+1,argtypes)
                else:
                    src = remove_expr(src,port2args,port,p,m.end(0),argtypes)

                match = True
            else:
                index = p+1
                
        m = re.search(port + '[ ]*\(([^\)]*)\)',src[index:])
        if m and re.search('[^a-zA-Z0-9_]',src[m.start(0)-1]):
            raise Exception("Cannot get data from input port '%s' more than one time in element '%s'."
                            % (port, funcname))

    # Replace output ports with function calls
    for o in output2func:
        m = re.search(o + '[ ]*\(',src)
        if m is None:
            raise Exception("Element '%s' never send data from output port '%s'." % (funcname,o))
        p = m.start(0)
        if p == 0 or re.search('[^a-zA-Z0-9_]',src[p-1]):
            (f, fport) = output2func[o]
            call = f
            if not(fport is None):
                call = call + '_' + fport
            src = src[:p] + call + src[p+len(o):]

    # Replace old state name with new state name
    for (old,new) in state_rename:
        match = True
        index = 0
        while match:
            match = re.search('[^a-zA-Z0-9_]('+old+').', src[index:])
            if match:
                src = src[:index+match.start(1)] + new + src[index+match.end(1):]
                index = index + match.start(1) + len(old)

    # Local state
    state_src = ""
    if local_state:
        state_src += "  struct Local { " + local_state.content + " };\n"
        state_src += "  static struct Local " + local_state.name
        if local_state.init:
            state_src += " = {" + local_state.init + "}"
        state_src += ";\n"

    # Construct function arguments from port2args.
    args = []
    for port in inports:
        args = args + port2args[port.name]

    src = "void " + funcname + "(" + ", ".join(args) + ") {\n" + state_src + src + "}\n"
    print src
    return src


def generate_state(state):
    src = ""
    src += "struct %s { %s };\n" % (state.name, state.content)
    print src
    return src


def generate_state_instance(name, state):
    src = ""
    src += "struct %s %s" % (state.name, name)
    if state.init:
        src += " = {%s}" % state.init
    src += ";\n"
    print src
    return src


def generate_signature(funcname, inports):
    n = len(inports)
    args = []
    src = ""
    for port in inports:
        args = args + port.argtypes
        if n > 1:
            src += "void %s_%s(%s);\n" % (funcname, port.name, ",".join(port.argtypes))

    src += "void %s(%s);" % (funcname, ",".join(args))
    print src
    return src


def get_element_port_arg_name(func, port, i):
    return "_%s_%s_arg%d" % (func, port, i)


def get_element_port_avail(func, port):
    return "_%s_%s_avail" % (func, port)


def generate_join_functions(funcname, inports):
    n = len(inports)
    src = ""
    if n > 1:
        avails = []
        clear = ""
        # Generate port available indicators.
        for port in inports:
            avail = get_element_port_avail(funcname, port.name)
            src += "int %s = 0;\n" % avail
            avails.append(avail)
            clear += "    %s = 0;\n" % avail

        # Generate buffer variables.
        buffers = []
        for port in inports:
            argtypes = port.argtypes
            for i in range(len(argtypes)):
                buffer = get_element_port_arg_name(funcname, port.name, i)
                src += "%s %s;\n" % (argtypes[i], buffer)
                buffers.append(buffer)

        # Generate code to invoke the main element and clear available indicators.
        all_avails = " && ".join(avails)
        all_buffers = ", ".join(buffers)
        invoke = "  if(%s) {\n" % all_avails
        invoke += clear
        invoke += "    %s(%s);\n" % (funcname, all_buffers)
        invoke += "  }\n"

        # Generate function for each input port.
        for port_id in range(len(inports)):
            port = inports[port_id]
            argtypes = port.argtypes

            # Function arguments.
            types_args = []
            args = []
            for i in range(len(argtypes)):
                args.append("arg%d" % (i))
                types_args.append("%s arg%d" % (argtypes[i], i))

            src += "void %s_%s(%s) {\n" % (funcname, port.name, ",".join(types_args))
            # Runtime check.
            src += "  if(%s == 1) { printf(\"Join failed (overwriting some values).\\n\"); exit(-1); }\n" \
                   % avails[port_id]
            for i in range(len(argtypes)):
                src += "  %s = %s;\n" % (get_element_port_arg_name(funcname, port.name, i), args[i])
            src += "  %s = 1;\n" % avails[port_id]
            src += invoke
            src += "}\n"

    print src
    return src


def generateCode(graph):
    # Generate states.
    for state in graph.states.values():
        generate_state(state)

    # Generate state instances.
    for name in graph.state_instances:
        generate_state_instance(name, graph.state_instances[name])

    # Generate signatures.
    for name in graph.instances:
        e = graph.instances[name].element
        generate_signature(name, e.inports)

    # Generate join functions.
    for name in graph.instances:
        e = graph.instances[name].element
        generate_join_functions(name, e.inports)

    # Generate functions.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        state_rename = []
        for i in range(len(instance.state_args)):
            state_rename.append((e.state_params[i][1],instance.state_args[i]))
        element_to_function(e.code, name, e.inports, instance.output2ele, e.local_state, state_rename)
