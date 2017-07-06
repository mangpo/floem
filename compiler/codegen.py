from join_handling import get_join_buffer_name
from codegen_thread import *
from codegen_state import generate_state_instances
import re, os, subprocess, time

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
    while i >= 0 and (s[i] == ' ' or s[i] == '\n'):
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
    while i < l and (s[i] == ' ' or s[i] == '\n'):
        i += 1

    if i < l:
        return (s[i],i)
    else:
        return (None,-1)


def remove_asgn_stmt(funcname, src, port2args,port,p_eq, p_end, inport_types):
    """
    Remove the reading from port statement from src, and put its LHS of the statement in port2args.
    (int x) = inp();
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
    if decl == '':
        argtypes = []
    else:
        args = decl.split(",")
        port2args[port] = args
        argtypes = [common.get_type(x) for x in args]

    if not(argtypes == inport_types):
        raise Exception("At element instance '%s', types mismatch at an input port '%s'. Expect %s, but got %s."
                        % (funcname, port, inport_types, argtypes))
        
    return src[:p_start] + src[p_end:]


def remove_nonasgn_stmt(funcname, src,port2args,port,p_start, p_end, inport_types):
    """
    Remove the reading from port statement from src,
    when the reading is not saved in any variable or used in any expression.
    inp();
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


def remove_expr(funcname, src,port2args,port,p_start, p_end, inport_types):
    """
    Remove the reading from port expression from src, and replace it with a fresh variable name.
    int x = inp() + 1;
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
        raise Exception("At element instance '%s', input port '%s' returns %d values. It cannot be used as an expression."
                        % (funcname, port,n))

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
            match = re.search('[^a-zA-Z0-9_]('+old+')[^a-zA-Z0-9_]', src[index:])
            if match:
                src = src[:index+match.start(1)] + new + src[index+match.end(1):]
                index = index + match.start(1) + len(old)
    return src


def element_to_function(instance, state_rename, graph, ext):
    """
    Turn an element into a function.
    - Read from an input port => input argument(s).
    - Write to an output port => a function call.
    :param instance:
    :param state_rename:
    :return: a string of function source code
    """
    element = instance.element
    src = element.get_code(instance.device[0])
    out_src = element.get_output_code(instance.join_partial_order, instance.device[0])
    funcname = instance.name
    inports = element.inports
    output2func = instance.output2ele

    # Create join buffer
    join_create = ""
    join_clean = ""
    for join in instance.join_state_create:
        join_buffer_name = get_join_buffer_name(join)
        join_create += "  %s *_p_%s = malloc(sizeof(%s));\n" % (join_buffer_name, join, join_buffer_name)
        # struct Vector *retVal = malloc (sizeof (struct Vector));
        join_clean += "  free(_p_%s);\n" % join

    # Call join element
    join_call_map = {}
    for join in instance.join_call:
        join_call = ""
        types, args = common.types_args_port_list(graph.instances[join].join_ports_same_thread,
                                                  "_p_%s->{0}_arg{1}" % join)

        if join in instance.API_return_from:
            join_call += "ret ="
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
        m = re.search('[^a-zA-Z0-9_](' + port + '[ ]*\(([^\)]*)\))', src)
        if m is None:
            m = re.search('(' + port + '[ ]*\(([^\)]*)\))', src)
        if m is None:
            continue

        p = m.start(1)
        check_no_args(m.group(2))
        c1, p1 = last_non_space(src, p)
        c2, p2 = first_non_space(src, m.end(1))
        c0, p0 = last_non_space(src, p1 - 1)

        if c0 == ')' and c1 == '=' and c2 == ';':
            src = remove_asgn_stmt(funcname, src, port2args, port, p1, p2 + 1, argtypes)
        elif (c1 == ';' or c1 is None) and c2 == ';':
            src = remove_nonasgn_stmt(funcname, src, port2args, port, p1 + 1, p2 + 1, argtypes)
        else:
            src = remove_expr(funcname, src, port2args, port, p, m.end(1), argtypes)
                
        m = re.search('[^a-zA-Z0-9_]' + port + '[ ]*\(([^\)]*)\)', src)
        if m:
            raise Exception("Cannot get data from input port '%s' more than one time in element '%s'."
                            % (port, funcname))

    # Respect instance.join_partial_order
    local_order = []
    for port in element.outports:
        if port.name not in instance.join_partial_order:
            local_order.append(port.name)
    local_order += instance.join_partial_order

    last_port = {}
    for name in local_order:
        if name in output2func:
            (f, fport) = output2func[name]
            if f in join_call_map:
                last_port[f] = name

    # Replace output ports with function calls
    if element.output_fire == "multi":
        # Batch element: replace inside main src
        for o in output2func:
            (f, fport) = output2func[o]
            m = re.search('[^a-zA-Z_0-9](' + o + ')[ ]*\([^;]*;', src)
            while m:
                src = src[:m.start(1)] + f + src[m.end(1):]
                m = re.search('[^a-zA-Z_0-9](' + o + ')[ ]*\([^;]*;', src)
    else:
        # Non-batch element: replace in out_src
        for o in output2func:
            m = re.search('(' + o + '[ ]*\()[^;]*;', out_src)
            if m is None:
                raise Exception("Element instance '%s' never send data from output port '%s'." % (funcname, o))
            (f, fport) = output2func[o]
            if o in instance.join_output2save:
                if isinstance(fport, list):
                    raise Exception(
                        "Join element instance '%s' has multiple input ports from one single port of an element instance '%s."
                        % (f, funcname))
                # Save output to join buffer instead of calling the next function
                join = instance.join_output2save[o]
                call = get_join_buffer_name(join) + "_" + fport + "_save(_p_" + join
                if not out_src[m.end(1)] == ")":
                    call += ", "

                # Insert join_call right after saving the buffer for it.
                # This is to preserve the right order of function calls.
                if f in join_call_map and last_port[f] == o:
                    out_src = out_src[:m.start(1)] + call + out_src[m.end(1):m.end(0)] + \
                              join_call_map[f] + out_src[m.end(0):]
                else:
                    out_src = out_src[:m.start(1)] + call + out_src[m.end(1):m.end(0)] + out_src[m.end(0):]
            else:
                out_inst = graph.instances[f]
                call = ""
                if f in instance.API_return_from:
                    call += "ret = "
                call += f + "(" + ','.join(["_p_%s" % j for j in out_inst.join_func_params])
                # for join in graph.instances[f].join_func_params:
                #     call += "_p_%s, " % join
                if len(out_inst.join_func_params) > 0 and out_inst.element.number_of_args() > 0:
                    call += ','
                out_src = out_src[:m.start(1)] + call + out_src[m.end(1):]


    # Replace API output port with function to create return state
    if instance.API_return_final:
        #o = instance.element.outports[0].name
        o = instance.API_return_final.return_port
        m = re.search(o + '[ ]*\(', out_src)
        if m is None:
            raise Exception("Element '%s' never send data from output port '%s'." % (funcname, o))
        p = m.start(0)
        call = "ret = _get_%s(" % (instance.API_return.replace('*','$').replace(' ', '_'))
        out_src = out_src[:p] + call + out_src[m.end(0):]

    # Replace old state name with new state name
    src = rename_state(state_rename, src)
    out_src = rename_state(state_rename, out_src)

    # Define return value
    define_ret = ""
    if instance.API_return:
        if instance.API_default_val:
            define_ret += "  %s ret = %s;\n" % (instance.API_return, instance.API_default_val)
        else:
            define_ret += "  %s ret;\n" % instance.API_return

    # API Return
    api_return = ""
    if instance.API_return:
        api_return += "  return ret;\n"

    # Construct function arguments from port2args.
    args = []
    # Join buffers
    for i in range(len(instance.join_func_params)):
        join = instance.join_func_params[i]
        args.append("%s* _p_%s" % (get_join_buffer_name(join), join))
    # Normal args
    id = 0
    for port in inports:
        if port.name in port2args:
            args = args + port2args[port.name]
        else:
            for type in port.argtypes:
                arg_type = "%s _unused%d" % (type, id)
                id += 1
                args.append(arg_type)

    if element.special == "from_net":
        args.append("cvmx_wqe_t *wqe")

    # Code
    if instance.API_return:
        return_type = instance.API_return
    else:
        return_type = "void"
    code = "%s %s(%s) {\n" % (return_type, funcname, ", ".join(args))
    code += join_create + src + define_ret + out_src + join_clean + element.cleanup + api_return
    code += "}\n"

    name = instance.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print code



def generate_state(state, graph, ext):
    if state.declare:
        src = ""
        src += "typedef struct _%s { %s } %s;" % (state.name, state.content, state.name)
        for process in graph.processes:
            name = process + ext
            with open(name, 'a') as f, redirect_stdout(f):
                print src


# def generate_state_instance(name, state_instance, ext):
#     state = state_instance.state
#     src = ""
#     src += "%s %s" % (state.name, name)
#     if state_instance.init:
#         ret = get_str_init(state_instance.init)
#         src += " = %s" % get_str_init(state_instance.init)
#     elif state.init:
#         src += " = %s" % get_str_init(state.init)
#     src += ";"
#     for process in state_instance.processes:
#         name = process + ext
#         with open(name, 'a') as f, redirect_stdout(f):
#             print src


def generate_join_save_function(name, join_ports_same_thread, instance, ext):
    src = ""

    st_name = get_join_buffer_name(name)
    for port in join_ports_same_thread:
        types_args, args = common.types_args_one_port(port, common.standard_arg_format)
        src += "void %s_%s_save(%s *p" % (st_name, port.name, st_name)
        if len(types_args) > 0:
            src += ", %s) {\n" % (", ".join(types_args))
        else:
            src += ") {\n"

        for arg in args:
            src += "  p->%s = %s;\n" % (arg, arg)
        src += "}\n"

    name = instance.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src


def generate_API_identity_macro(api, ext):
    src = "#define _get_%s(X) X" % api.return_type.replace('*', '$').replace(' ', '_')
    name = api.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src


def generate_API_function(api, ext):
    args = []
    types_args = []
    if api.call_types:
        for i in range(len(api.call_types)):
            arg = "arg" + str(i)
            args.append(arg)
            types_args.append("%s %s" % (api.call_types[i], arg))

    src = ""
    if api.return_port:
        src += "%s %s(%s) { " % (api.return_type, api.name, ", ".join(types_args))
        src += "return %s(%s); }\n" % (api.call_instance, ", ".join(args))
        header_src = "%s %s(%s);\n" % (api.return_type, api.name, ", ".join(types_args))
    else:
        src += "void %s(%s) { " % (api.name, ", ".join(types_args))
        src += "%s(%s); }\n" % (api.call_instance, ", ".join(args))
        header_src = "void %s(%s);\n" % (api.name, ", ".join(types_args))

    if ext == '.h':
        with open(api.process + '.h', 'a') as f, redirect_stdout(f):
            print header_src

    with open(api.process + '.c', 'a') as f, redirect_stdout(f):
        print src


def generate_signature(instance, funcname, inports, ext):
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

    name = instance.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src


def get_element_port_arg_name(func, port, i):
    return "_%s_%s_arg%d" % (func, port, i)


def get_element_port_avail(func, port):
    return "_%s_%s_avail" % (func, port)


def generate_header_h(testing, graph):
    for process in graph.processes:
        device = graph.process2device[process]
        if device == target.CPU:
            src = ""
            for file in target.cpu_include_h:
                src += "#include %s\n" % file

        elif device == target.CAVIUM:
            src = ""
            for file in target.cavium_include_h:
                src += "#include %s\n" % file

        name = process + '.h'
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def generate_header_c(testing, graph):
    for process in graph.processes:
        device = graph.process2device[process]
        if device == target.CPU:
            src = ""
            for file in target.cpu_include_c:
                src += "#include %s\n" % file

            src += common.pipeline_include

            if testing:
                src += "void out(int x) { printf(\"%d\\n\", x); }"
        elif device == target.CAVIUM:
            src = ""
            for file in target.cavium_include_c:
                src += "#include %s\n" % file

            src += common.pipeline_include

        name = process + '.c'
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def generate_include(include, processes, ext):
    if include:
        for process in processes:
            name = process + ext
            with open(name, 'a') as f, redirect_stdout(f):
                print include


def generate_code(graph, ext, testing=None, include=None):
    """
    Display C code to stdout
    :param graph: data-flow graph
    """

    if ext == '.h':
        generate_header_h(testing, graph)
    generate_header_c(testing, graph)
    if ext == '.h':
        generate_include(include, graph.processes, '.h')
    generate_include(include, graph.processes, '.c')

    # Generate memory regions.
    generate_memory_regions(graph, ext)

    # Generate states.
    for state_name in graph.state_order:
        generate_state(graph.states[state_name], graph, ext)

    # Generate state instances.
    generate_state_instances(graph, '.c')
    # for name in graph.state_instance_order:
    #     generate_state_instance(name, graph.state_instances[name], ext)

    # Generate functions to save join buffers.
    for instance in graph.instances.values():
        if instance.join_ports_same_thread:
            generate_join_save_function(instance.name, instance.join_ports_same_thread, instance, '.c')

    # Generate functions to produce API return state
    return_funcs = []
    for api in graph.threads_API:
        if api.return_type and api.return_type not in return_funcs:
            return_funcs.append(api.return_type)
            generate_API_identity_macro(api, '.c')

    # Generate signatures.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        generate_signature(instance, name, e.inports, '.c')

    # Generate functions.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        state_rename = []
        for i in range(len(instance.state_args)):
            state_rename.append((e.state_params[i][1],instance.state_args[i]))
        element_to_function(instance, state_rename, graph, '.c')

    # Generate API functions.
    for api in graph.threads_API:
        generate_API_function(api, ext)


def convert_type(result, expect):
    if isinstance(expect, int):
        return int(result)
    elif isinstance(expect, float):
        return float(result)
    else:
        return result


def define_header(graph):
    for process in graph.processes:
        with open(process + '.h', 'a') as f, redirect_stdout(f):
            print "#ifndef %s_H" % process.upper()
            print "#define %s_H" % process.upper()

        with open(process + '.c', 'a') as f, redirect_stdout(f):
            print '#include "%s.h"' % process


def end_header(graph):
    for process in graph.processes:
        with open(process + '.h', 'a') as f, redirect_stdout(f):
            print "#endif"


def remove_files(graph, ext):
    for process in graph.processes:
        name = process + ext
        os.system("rm " + name)

def generate_code_only(graph, testing, mode, include=None):
    remove_files(graph, ".c")
    generate_code(graph, ".c", testing, include)
    generate_inject_probe_code(graph, ".c")
    generate_internal_triggers(graph, ".c", mode)

def generate_code_as_header(graph, testing, mode, include=None):
    remove_files(graph, ".h")
    remove_files(graph, ".c")
    define_header(graph)
    generate_code(graph, ".h", testing, include)
    generate_inject_probe_code(graph, ".h")
    generate_internal_triggers(graph, ".h", mode)
    end_header(graph)


def generate_code_and_compile(graph, testing, mode, include=None, depend=None):
    remove_files(graph, ".c")
    generate_code(graph, ".c", testing, include)
    generate_inject_probe_code(graph, ".c")
    generate_internal_triggers(graph, ".c", mode)
    generate_testing_code(graph, testing, ".c")

    extra = ""
    if depend:
        for f in depend:
            extra += '%s.o ' % f
            cmd = 'gcc -O3 -msse4.1 -I %s -c %s.c -lrt' % (common.dpdk_include, f)
            #cmd = 'gcc -O3 -msse4.1 -I %s -c %s.c' % (common.dpdk_include, f)
            status = os.system(cmd)
            if not status == 0:
                raise Exception("Compile error: " + cmd)

    for process in graph.processes:
        cmd = 'gcc -O3 -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % (common.dpdk_include, process, extra, process)
        #cmd = 'gcc -O3 -msse4.1 -I %s -pthread %s.c %s -o %s' % (common.dpdk_include, process, extra, process)
        status = os.system(cmd)
        if not status == 0:
            raise Exception("Compile error: " + cmd)


def generate_code_and_run(graph, testing, mode, expect=None, include=None, depend=None):
    generate_code_and_compile(graph, testing, mode, include, depend)

    if expect:
        assert (len(graph.processes) == 1 and graph.processes == set(["tmp"])), \
            "generate_code_and_run doesn't support multiple processes. Please use generate_code_and_compile()"
        try:
            result = subprocess.check_output('./tmp', stderr=subprocess.STDOUT, shell=True)
            result = result.split()
            if not len(result) == len(expect):
                raise Exception("Expect %s. Actual %s." % (expect, result))
            for i in range(len(expect)):
                convert = convert_type(result[i], expect[i])
                if not expect[i] == convert:
                    raise Exception("Expect %d. Actual %d." % (expect[i], convert))
        except subprocess.CalledProcessError as e:
            print e.output
            raise e
        except Exception as e:
            raise e

    else:
        try:
            master_process = graph.master_process
            if not master_process:
                master_process = graph.default_process
            ps = []
            p = subprocess.Popen(['./' + master_process])
            ps.append(p)
            for process in graph.processes:
                if process is not graph.master_process:
                    #result = subprocess.check_output('./' + process, stderr=subprocess.STDOUT, shell=True)
                    p = subprocess.Popen(['./' + process])
                    ps.append(p)

            time.sleep(0.1)
            for p in ps:
                p.kill()
        except subprocess.CalledProcessError as e:
            print e.output
            raise e
        except Exception as e:
            raise e

    print "PASSED!"


def compile_object_file(f):
    if isinstance(f, str):
        cmd = 'gcc -O0 -g -msse4.1 -I %s -c %s.c -lrt' % (common.dpdk_include, f)
        print cmd
        status = os.system(cmd)
        if not status == 0:
            raise Exception("Compile error: " + cmd)
    elif isinstance(f, list):
        for fi in f:
            compile_object_file(fi)
    elif isinstance(f, dict):
        s = set()
        for l in f.values():
            s = s.union(set(l))
        compile_object_file([si for si in s])

def compile_and_run(name, depend):
    compile_object_file(depend)

    if isinstance(name, str):
        cmd = 'gcc -O0 -g -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % \
              (common.dpdk_include, name, ' '.join([d + '.o' for d in depend]), name)
        print cmd
        status = os.system(cmd)
        if not status == 0:
            raise Exception("Compile error: " + cmd)
        status = os.system('./%s' % name)
        if not status == 0:
            raise Exception("Runtime error")

        print "PASSED!"

    elif isinstance(name, list):
        for f in name:
            if isinstance(f, tuple):
                f = f[0]
            cmd = 'gcc -O0 -g -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % \
                  (common.dpdk_include, f, ' '.join([d + '.o' for d in depend[f]]), f)
            print cmd
            status = os.system(cmd)
            if not status == 0:
                raise Exception("Compile error: " + cmd)

        ps = []
        for f in name:
            if isinstance(f, str):
                cmd = ['./' + f]
            else:
                cmd = [str(x) for x in f]
                cmd[0] = './' + cmd[0]
            print cmd
            p = subprocess.Popen(cmd)
            ps.append(p)

        time.sleep(5)
        for p in ps:
            p.kill()

