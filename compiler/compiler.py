from program import *
from join_handling import get_join_buffer_name, annotate_join_info
from api_handling import annotate_api_info
import re, sys, os, subprocess
from contextlib import contextmanager


@contextmanager
def redirect_stdout(new_target):
    old_target, sys.stdout = sys.stdout, new_target # replace sys.stdout
    try:
        yield new_target # run some code with the replaced stdout
    finally:
        sys.stdout = old_target # restore to the previous value

var_id = 0
def fresh_var_name():
    global var_id
    name = '_x' + str(var_id)
    var_id += 1
    return name


def check_no_args(args):
    if not(args == ""):
        raise Exception("Cannot pass an argument when retrieving data from an input port.")


def last_non_space(s,i):
    """
    :param s: string
    :param i: index
    :return: A pair of (the last character before s[i] that is not a space, its index)
    """
    i -= 1
    while i >= 0 and s[i] == ' ':
        i -= 1

    if i >= 0:
        return (s[i],i)
    else:
        return (None,-1)


def first_non_space(s,i):
    """
    :param s: string
    :param i: index
    :return: A pair of (the first character start from s[i] that is not a space, its index)
    """
    l = len(s)
    while i < l and s[i] == ' ':
        i += 1

    if i < l:
        return (s[i],i)
    else:
        return (None,-1)


def remove_asgn_stmt(src,port2args,port,p_eq, p_end, inport_types):
    """
    Remove the reading from port statement from src, and put its LHS of the statement in port2args.
    :param src:       string source code
    :param port2args: map port name to a list of (type,argument name)
    :param port:      port name
    :param p_eq:      position of '=' of the statement to be removed
    :param p_end:     the ending position of the statement to be removed (after ';')
    :param inport_types: data types of the port
    :return: updated code
    """
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


def remove_nonasgn_stmt(src,port2args,port,p_start, p_end, inport_types):
    """
    Remove the reading from port statement from src,
    when the reading is not saved in any variable or used in any expression.
    :param src:       string source code
    :param port2args: map port name to a list of (type,argument name)
    :param port:      port name
    :param p_start:   the starting position of the statement to be removed
                      (after previous ';' or 0 if no previous ';')
    :param p_end:     the ending position of the statement to be removed (after ';')
    :param inport_types: data types of the port
    :return: updated code
    """
    args = [t + ' ' + fresh_var_name() for t in inport_types]
    port2args[port] = args
    return src[:p_start] + src[p_end:]


def remove_expr(src,port2args,port,p_start, p_end, inport_types):
    """
    Remove the reading from port expression from src, and replace it with a fresh variable name.
    :param src:       string source code
    :param port2args: map port name to a list of (type,argument name)
    :param port:      port name
    :param p_start:   the starting position of the expression to be removed
    :param p_end:     the ending positiion of the statement to be removed (after ')')
    :param inport_types: data types of the port
    :return: updated code
    """
    n = len(inport_types)
    if n > 1 or n == 0:
        raise Exception("Input port '%s' returns %d values. It cannot be used as an expression." % (port,n))

    name = fresh_var_name()
    port2args[port] = [inport_types[0] + ' ' + name]
    return src[:p_start] + name + src[p_end:]


def rename_state(rename, src):
    """
    Given a list of (old_str, new_str), replace old_strin src with new_str.
    :param rename: a list of (old_str, new_str)
    :param src: code
    :return: renamed src
    """
    for (old, new) in rename:
        match = True
        index = 0
        while match:
            match = re.search('[^a-zA-Z0-9_]('+old+').', src[index:])
            if match:
                src = src[:index+match.start(1)] + new + src[index+match.end(1):]
                index = index + match.start(1) + len(old)
    return src

def element_to_function(instance, state_rename, graph):
    """
    Turn an element into a function.
    - Read from an input port => input argument(s).
    - Write to an output port => a function call.
    :param instance:
    :param state_rename:
    :return: a string of function source code
    """
    element = instance.element
    src = element.code
    out_src = element.get_output_code(instance.join_partial_order)
    funcname = instance.name
    inports = element.inports
    output2func = instance.output2ele
    local_state = element.local_state

    # Create join buffer
    join_create = ""
    for join in instance.join_state_create:
        join_buffer_name = get_join_buffer_name(join)
        join_create += "  %s *_p_%s = malloc(sizeof(%s));\n" % (join_buffer_name, join, join_buffer_name)
        # struct Vector *retVal = malloc (sizeof (struct Vector));

    # Call join element
    join_call_map = {}
    for join in instance.join_call:
        join_call = ""
        types, args = common.types_args_port_list(graph.instances[join].join_ports_same_thread,
                                                  "_p_%s->{0}_arg{1}" % join)

        if instance.API_return_from == join:
            join_call += "%s ret =" % instance.API_return
        join_call += "  %s(" % join
        for other_join in graph.instances[join].join_func_params:
            join_call += "_p_%s, " % other_join
        join_call += ", ".join(args)
        join_call += ");\n"
        join_call_map[join] = join_call

    src += '\n'
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
        m = re.search('(' + o + '[ ]*\()[^)]*\)[ ]*;', out_src)
        if m is None:
            raise Exception("Element '%s' never send data from output port '%s'." % (funcname,o))
        (f, fport) = output2func[o]
        if o in instance.join_output2save:
            if isinstance(fport, list):
                raise Exception(
                    "Join element instance '%s' has multiple input ports from one single port of an element instance '%s."
                    % (f, funcname))
            # Save output to join buffer instead of calling the next function
            join = instance.join_output2save[o]
            call = get_join_buffer_name(join) + "_" + fport + "_save(_p_" + join + ", "

            # Insert join_call right after saving the buffer for it.
            # This is to preserve the right order of function calls.
            if f in join_call_map:
                out_src = out_src[:m.start(1)] + call + out_src[m.end(1):m.end(0)] + \
                          join_call_map[f] + out_src[m.end(0):]
            else:
                out_src = out_src[:m.start(1)] + call + out_src[m.end(1):m.end(0)] + out_src[m.end(0):]
        else:
            call = ""
            if instance.API_return_from == f:
                call += "%s ret = " % instance.API_return
            call += f + "("
            for join in graph.instances[f].join_func_params:
                call += "_p_%s, " % join
            out_src = out_src[:m.start(1)] + call + out_src[m.end(1):]

    # Replace API output port with function to create return state
    if instance.API_return_final:
        #o = instance.element.outports[0].name
        o = instance.API_return_final.return_port
        m = re.search(o + '[ ]*\(', out_src)
        if m is None:
            raise Exception("Element '%s' never send data from output port '%s'." % (funcname, o))
        p = m.start(0)
        call = "%s ret = _get_%s(" % (instance.API_return, instance.API_return)
        out_src = out_src[:p] + call + out_src[m.end(0):]

    # Replace old state name with new state name
    src = rename_state(state_rename, src)
    out_src = rename_state(state_rename, out_src)

    # API Return
    api_return = ""
    if instance.API_return:
        api_return += "  return ret;\n"

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
    # Join buffers
    for i in range(len(instance.join_func_params)):
        join = instance.join_func_params[i]
        args.append("%s* _p_%s" % (get_join_buffer_name(join), join))
    # Normal args
    for port in inports:
        args = args + port2args[port.name]

    # Code
    if instance.API_return:
        return_type = instance.API_return
    else:
        return_type = "void"
    code = "%s %s(%s) {\n" % (return_type, funcname, ", ".join(args))
    code += state_src + join_create + src + out_src + api_return
    code += "}\n"
    print code
    return code


def generate_state(state):
    src = ""
    src += "typedef struct { %s } %s;" % (state.content, state.name)
    print src
    return src


def generate_state_instance(name, state):
    src = ""
    src += "%s %s" % (state.name, name)
    if state.init:
        src += " = {%s}" % state.init
    src += ";"
    print src
    return src


def generate_join_save_function(name, join_ports_same_thread):
    src = ""

    st_name = get_join_buffer_name(name)
    for port in join_ports_same_thread:
        types_args, args = common.types_args_one_port(port, common.standard_arg_format)
        src += "void %s_%s_save(%s *p, %s) {\n" % (st_name, port.name, st_name, ", ".join(types_args))
        for arg in args:
            src += "  p->%s = %s;\n" % (arg, arg)
        src += "}\n"

    print src
    return src


def generate_API_return_state(api, g):
    types_args = []
    args = []
    for port in g.instances[api.return_instance].element.outports:
        if port.name == api.return_port:
            l_types_args, l_args = common.types_args_one_port(port, common.standard_arg_format)
            types_args += l_types_args
            args += l_args

    src = ""
    src += "%s _get_%s(%s) {\n" % (api.state_name, api.state_name, ", ".join(types_args))
    src += "  %s ret = {%s};\n" % (api.state_name, ", ".join(args))
    src += "  return ret; }\n"
    print src
    return src


def generate_API_identity_macro(api):
    src = "#define _get_%s(X) X" % api.state_name
    print src
    return src


def generate_API_function(api, g):
    args = []
    types_args = []
    if api.call_port:
        instance = g.instances[api.call_instance]
        port = [port for port in instance.element.inports if port.name == api.call_port][0]
        types_args, args = common.types_args_one_port(port, "arg{1}")

    src = ""
    if api.return_port:
        src += "%s %s(%s) { " % (api.state_name, api.name, ", ".join(types_args))
        src += "return %s(%s); }\n" % (api.call_instance, ", ".join(args))
    else:
        src += "void %s(%s) { " % (api.name, ", ".join(types_args))
        src += "%s(%s); }\n" % (api.call_instance, ", ".join(args))
    print src
    return src


def generate_signature(instance, funcname, inports):
    n = len(inports)
    args = []
    src = ""
    # Join buffers
    for join in instance.join_func_params:
        args.append(get_join_buffer_name(join) + "*")
    # Normal args
    for port in inports:
        args += port.argtypes

    if instance.API_return:
        src += "%s %s(%s);" % (instance.API_return, funcname, ",".join(args))
    else:
        src += "void %s(%s);" % (funcname, ",".join(args))
    print src
    return src


def get_element_port_arg_name(func, port, i):
    return "_%s_%s_arg%d" % (func, port, i)


def get_element_port_avail(func, port):
    return "_%s_%s_avail" % (func, port)


def generate_graph(program, resource=True):
    """
    Compile program to data-flow graph and insert necessary elements for resource mapping and join elements.
    :param program: program AST
    :param resource: True if compile with resource mapping
    :return: data-flow graph
    """
    # Generate data-flow graph.
    gen = GraphGenerator()
    gen.interpret(program)
    gen.graph.check_input_ports()

    if resource:
        # Insert necessary elements for resource mapping.
        gen.allocate_resources()
        # Annotate APIs information. APIs ony make sense with resource mapping.
        annotate_api_info(gen.graph)
    else:
        gen.graph.clear_APIs()

    # Annotate join information
    annotate_join_info(gen.graph)

    return gen.graph


def generate_header(testing):
    src = "#include <stdio.h>\n"
    src += "#include <stdlib.h>\n\n"
    if testing:
        src += "void out(int x) { printf(\"%d\\n\", x); }"
    print src
    return src


def generate_testing_code(code):
    src = ""
    if code:
        src += "int main() {\n"
        src += "  " + code
        src += "\n  return 0;\n"
        src += "}\n"
    print src
    return src


def generate_code(graph, testing=False):
    """
    Display C code to stdout
    :param testing:
    :param graph: data-flow graph
    """
    generate_header(testing)

    # Generate states.
    for state in graph.states.values():
        generate_state(state)

    # Generate state instances.
    for name in graph.state_instances:
        generate_state_instance(name, graph.state_instances[name])

    # Generate functions to save join buffers.
    for instance in graph.instances.values():
        if instance.join_ports_same_thread:
            generate_join_save_function(instance.name, instance.join_ports_same_thread)

    # Generate functions to produce API return state
    return_funcs = []
    for api in graph.APIs:
        if api.state_name and api.state_name not in return_funcs:
            return_funcs.append(api.state_name)
            if api.state_name in common.primitive_types or not api.new_state_type:
                generate_API_identity_macro(api)
            else:
                generate_API_return_state(api, graph)

    # Generate signatures.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        generate_signature(instance, name, e.inports)

    # Generate functions.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        state_rename = []
        for i in range(len(instance.state_args)):
            state_rename.append((e.state_params[i][1],instance.state_args[i]))
        element_to_function(instance, state_rename, graph)

    # Generate API functions.
    for api in graph.APIs:
        generate_API_function(api, graph)

    generate_testing_code(testing)

def convert_type(result, expect):
    if isinstance(expect, int):
        return int(result)
    elif isinstance(expect, float):
        return float(result)
    else:
        return result

def generate_code_and_run(graph, testing, expect):
    with open('tmp.c', 'w') as f, redirect_stdout(f):
        generate_code(graph, testing)
    status = os.system('gcc -O3 tmp.c -o tmp')
    if not status == 0:
        raise Exception("Compile error.")
    result = subprocess.check_output('./tmp', shell=True).split()

    if not len(result) == len(expect):
        raise Exception("Expect %s. Actual %s." % (expect, result))
    for i in range(len(expect)):
        convert = convert_type(result[i], expect[i])
        if not expect[i] == convert:
            raise Exception("Expect %d. Actual %d." % (expect[i], convert))
