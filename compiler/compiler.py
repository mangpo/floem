from program import *
from join_handling import get_join_buffer_name, annotate_join_info
from api_handling import annotate_api_info
from process_handling import annotate_process_info
from pipeline_state import compile_pipeline_states
import re, sys, os, subprocess, time
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


def remove_asgn_stmt(funcname, src,port2args,port,p_eq, p_end, inport_types):
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
    argtypes = [common.get_type(x) for x in args]

    if not(argtypes == inport_types):
        raise Exception("At element instance '%s', types mismatch at an input port '%s'. Expect %s, but got %s."
                        % (funcname, port, inport_types, argtypes))
        
    return src[:p_start] + src[p_end:]


def remove_nonasgn_stmt(funcname, src,port2args,port,p_start, p_end, inport_types):
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


def remove_expr(funcname, src,port2args,port,p_start, p_end, inport_types):
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
        match = False
        index = 0
        while not(match):
            m = re.search(port + '[ ]*\(([^\)]*)\)',src[index:])
            if m == None:
                raise Exception("Element '%s' never gets data from input port '%s'." % (funcname,port))
            p = m.start(0)
            if p == 0 or re.search('[^a-zA-Z0-9_]',src[p-1]):
                check_no_args(m.group(1))
                c1, p1 = last_non_space(src,p)
                c2, p2 = first_non_space(src,m.end(0))
                c0, p0 = last_non_space(src,p1-1)

                if c0 == ')' and c1 == '=' and c2 == ';':
                    src = remove_asgn_stmt(funcname, src,port2args,port,p1,p2+1,argtypes)
                elif (c1 == ';' or c1 is None) and c2 == ';':
                    src = remove_nonasgn_stmt(funcname, src,port2args,port,p1+1,p2+1,argtypes)
                else:
                    src = remove_expr(funcname, src,port2args,port,p,m.end(0),argtypes)

                match = True
            else:
                index = p+1
                
        m = re.search(port + '[ ]*\(([^\)]*)\)',src[index:])
        if m and re.search('[^a-zA-Z0-9_]',src[m.start(0)-1]):
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
    for o in output2func:
        m = re.search('(' + o + '[ ]*\()[^;]*;', out_src)
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
            call = ""
            if f in instance.API_return_from:
                call += "ret = "
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
        call = "ret = _get_%s(" % (instance.API_return.replace('*','$'))
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
    code += state_src + join_create + src + define_ret + out_src + api_return
    code += "}\n"

    name = instance.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print code


def generate_memory_regions(graph, ext):
    master_src = ""
    slave_src = ""

    for region in graph.memory_regions:
        master_src += 'void *%s;\n' % region.name
        slave_src += 'void *%s;\n' % region.name

    master_src += "void init_memory_regions() {\n"
    slave_src += "void init_memory_regions() {\n"

    for region in graph.memory_regions:
        master_src += '  %s = util_create_shmsiszed("%s", %d);\n' % (region.name, region.name, region.size)
        slave_src += '  %s = util_map_shm("%s", %d);\n' % (region.name, region.name, region.size)

    master_src += "}\n"
    slave_src += "}\n"

    master_src += "void finalize_memory_regions() {\n"
    slave_src += "void finalize_memory_regions() {\n"

    for region in graph.memory_regions:
        master_src += '  shm_unlink("%s");\n' % region.name
        master_src += '  munmap(%s, %d);\n' % (region.name, region.size)
        slave_src += '  munmap(%s, %d);\n' % (region.name, region.size)

    master_src += "}\n"
    slave_src += "}\n"

    with open(graph.master_process + ext, 'a') as f, redirect_stdout(f):
        print master_src

    for process in graph.processes:
        if process is not graph.master_process:
            with open(process + ext, 'a') as f, redirect_stdout(f):
                print slave_src


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

def declare_state(name, state_instance, ext):
    state = state_instance.state
    src = ""
    src += "{0}* {1};\n".format(state.name, name)
    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def init_value(val):
    if isinstance(val, AddressOf):
        return '&' + val.of
    else:
        return val


def map_shared_state(name, state_instance, ext):
    state = state_instance.state
    src = "{1} = ({0} *) shm_p;\n".format(state.name, name)
    src += "shm_p = shm_p + sizeof({0});\n".format(state.name)

    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def allocate_state(name, state_instance, ext):
    state = state_instance.state
    src = "{1} = ({0} *) malloc(sizeof({0}));\n".format(state.name, name)

    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def init_state(name, state_instance, master, all_processes, ext):
    state = state_instance.state
    src = ""
    if state_instance.init or state.init:
        if state_instance.init:
            inits = state_instance.init
        else:
            inits = state.init
        for i in range(len(state.fields)):
            field = state.fields[i]
            init = inits[i]
            if isinstance(init, list):
                if init == [0]:
                    pass  # Default is all zeros
                else:
                    m = re.match('([a-zA-Z0-9_]+)\[[0-9]+\]', field)
                    array = m.group(1)
                    for i in range(len(init)):
                        src += "{0}->{1}[{2}] = {3};\n".format(name, array, i, init_value(init[i]))
            else:
                src += "{0}->{1} = {2};\n".format(name, field, init_value(init))

    if len(state_instance.processes) <= 1:
        process = [x for x in state_instance.processes][0]
    else:
        process = master
    name = process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src


def generate_state_instances(graph, ext):

    # Declare states
    for name in graph.state_instance_order:
        declare_state(name, graph.state_instances[name], ext)

    # Collect shared memory
    shared = set()
    #total_size = 0
    all_processes = set()
    for name in graph.state_instance_order:
        inst = graph.state_instances[name]
        if len(inst.processes) > 1:
            #size = inst.state.size  # TODO
            #shared[name] = size
            #total_size += size
            shared.add(name)
            all_processes = all_processes.union(inst.processes)

    all_processes = [x for x in all_processes]

    src = "size_t shm_size = 0;\n"
    src += "void *shm;\n"
    src += "void init_state_instances() {\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src

    # Create shared memory
    if len(all_processes) > 1:
        # Check processes
        assert (graph.master_process in graph.processes), "Please specify a master process using master_process(name)."

        shared_src = ""
        for name in shared:
            inst = graph.state_instances[name]
            shared_src += "shm_size += sizeof(%s);\n" % inst.state.name
        master_src = 'shm = util_create_shmsiszed("SHARED", shm_size);\n'
        master_src += 'uintptr_t shm_p = (uintptr_t) shm;'
        slave_src = 'shm = util_map_shm("SHARED", shm_size);\n'
        slave_src += 'uintptr_t shm_p = (uintptr_t) shm;'
        with open(graph.master_process + ext, 'a') as f, redirect_stdout(f):
            print shared_src
            print master_src
        for process in all_processes:
            if process is not graph.master_process:
                name = process + ext
                with open(name, 'a') as f, redirect_stdout(f):
                    print shared_src
                    print slave_src

    # Initialize states
    for name in graph.state_instance_order:
        inst = graph.state_instances[name]
        if name in shared:
            map_shared_state(name, inst, ext)
        else:
            allocate_state(name, inst, ext)
        init_state(name, inst, graph.master_process, all_processes, ext)

    src = "}\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src

    src = "void finalize_state_instances() {\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src

    if len(all_processes) > 1:
        master_src = 'shm_unlink("SHARED");\n'
        with open(graph.master_process + ext, 'a') as f, redirect_stdout(f):
            print master_src

        src = 'munmap(shm, shm_size);\n'
        for process in all_processes:
            name = process + ext
            with open(name, 'a') as f, redirect_stdout(f):
                print src

    src = "}\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


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


# def generate_API_return_state(api, g):
#     types_args = []
#     args = []
#     for port in g.instances[api.return_instance].element.outports:
#         if port.name == api.return_port:
#             l_types_args, l_args = common.types_args_one_port(port, common.standard_arg_format)
#             types_args += l_types_args
#             args += l_args
#
#     src = ""
#     src += "%s _get_%s(%s) {\n" % (api.state_name, api.state_name.replace('*','$'), ", ".join(types_args))
#     src += "  %s ret = {%s};\n" % (api.state_name, ", ".join(args))
#     src += "  return ret; }\n"
#     print src
#     return src


def generate_API_identity_macro(api, ext):
    src = "#define _get_%s(X) X" % api.return_type.replace('*', '$')
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
    else:
        src += "void %s(%s) { " % (api.name, ", ".join(types_args))
        src += "%s(%s); }\n" % (api.call_instance, ", ".join(args))

    name = api.process + ext
    with open(name, 'a') as f, redirect_stdout(f):
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


def program_to_graph_pass(program, default_process="tmp"):
    # Generate data-flow graph.
    gen = GraphGenerator(default_process)
    gen.interpret(program)
    return gen


def pipeline_state_pass(gen, check=True):
    # Annotate minimal join information
    annotate_join_info(gen.graph, False)
    compile_pipeline_states(gen.graph, check)


def join_and_resource_annotation_pass(gen, resource, remove_unused):
    if resource:
        # Insert necessary elements for resource mapping.
        # Assign call_instance for each thread.
        # Check that one thread has one starting element.
        # Impose control dependence order.
        gen.allocate_resources()
    else:
        gen.graph.clear_APIs()

    if remove_unused:
        gen.graph.remove_unused_elements(resource)

    # Annotate detaile join information
    annotate_join_info(gen.graph, True)

    if resource:
        # Annotate APIs information. APIs ony make sense with resource mapping.
        annotate_api_info(gen.graph)

    annotate_process_info(gen.graph)

    if remove_unused:
        gen.graph.remove_unused_states()


def generate_graph(program, resource=True, remove_unused=False, default_process="tmp"):
    """
    Compile program to data-flow graph and insert necessary elements for resource mapping and join elements.
    :param program: program AST
    :param resource: True if compile with resource mapping
    :return: data-flow graph
    """
    gen = program_to_graph_pass(program, default_process)
    pipeline_state_pass(gen)
    join_and_resource_annotation_pass(gen, resource, remove_unused)

    return gen.graph


def generate_header(testing, processes, ext):
    src = ""
    for file in common.header_files + common.header_files_triggers:
        src += "#include <%s>\n" % file

    if testing:
        src += "void out(int x) { printf(\"%d\\n\", x); }"

    for process in processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def generate_include(include, processes, ext):
    if include:
        for process in processes:
            name = process + ext
            with open(name, 'a') as f, redirect_stdout(f):
                print include

n_threads = 0
def thread_func_create_cancel(func, size=None):
    thread = "pthread_t _thread_%s;\n" % func
    if size:
        func_src = r'''
            void *_run_%s(void *threadid) {
                usleep(100000);
                for(int i=0; i<%d; i++) {
                    //printf("inject = %s\n", i);
                    %s();
                    usleep(50); }
                pthread_exit(NULL);
            }''' % (func, size, '%d', func)
    else:
        func_src = "void *_run_%s(void *threadid) { while(true) { %s(); /* usleep(1000); */ } }\n" % (func, func)
    create = "  pthread_create(&_thread_%s, NULL, _run_%s, NULL);\n" % (func, func)
    cancel = "  pthread_cancel(_thread_%s);\n" % func
    return (thread, func_src, create, cancel)


def is_spec_impl(threads):
    if len(threads) == 0:
        return False

    for t in threads:
        m = (re.match('_spec', t) or re.match('_impl', t))
        if not m:
            return False
    return True


def inject_thread_code(injects):
    global_src = ""
    run_src = ""
    kill_src = ""

    for (func, size) in injects:
        (thread, func_src, create, cancel) = thread_func_create_cancel(func, size)
        global_src += thread
        global_src += func_src
        run_src += create
        kill_src += cancel

    return global_src, run_src, kill_src


def internal_thread_code(forever, graph):
    global_src = ""
    run_src = ""
    kill_src = ""

    for func in forever:
        if len(graph.instances[func].element.inports) > 0:
            raise Exception("The element '%s' cannot be a starting element because it receives an input from another element." % func)

        (thread, func_src, create, cancel) = thread_func_create_cancel(func)
        global_src += thread
        global_src += func_src
        run_src += create
        kill_src += cancel

    return global_src, run_src, kill_src


# for state_instance in injects:
#     if process in graph.state_instances[state_instance].processes:
#         inject = injects[state_instance]

def generate_internal_triggers_with_process(graph, process, ext):
    threads_internal = set([trigger.call_instance for trigger in graph.threads_internal])
    threads_api = set([trigger.call_instance for trigger in graph.threads_API])
    injects = graph.inject_populates

    spec_injects = []
    impl_injects = []
    all_injects = []
    for state_instance in injects:
        #if process in graph.state_instances[state_instance].processes:
        inject = injects[state_instance]
        spec_injects += [(x, inject.size) for x in inject.spec_ele_instances if process == graph.instances[x].process]
        impl_injects += [(x, inject.size) for x in inject.impl_ele_instances if process == graph.instances[x].process]
        all_injects += [x for x in inject.spec_ele_instances if process == graph.instances[x].process]
        all_injects += [x for x in inject.impl_ele_instances if process == graph.instances[x].process]

    spec_impl = is_spec_impl(threads_internal.union(all_injects))

    forever = threads_internal.difference(all_injects)
    no_triggers = graph.threads_roots.difference(forever).difference(all_injects).difference(threads_api)

    forever = [t for t in forever if graph.instances[t].process == process]
    no_triggers = [t for t in no_triggers if graph.instances[t].process == process]
    if len(no_triggers) > 0:
        for inst in no_triggers:
            t = graph.instances[inst].thread
            if t:
                raise Exception(
                    "Element instance '%s' is assigned to thread '%s', but it is not reachable from the starting element of thread '%s'.\n"
                    % (inst, t, t)
                    + "To make it reachable, use %s.run_order to specify an order from an element reachable by the starting element of thread '%s' to '%s'."
                    % (t, t, inst)
                )

    if not spec_impl:
        g1, r1, k1 = inject_thread_code(spec_injects + impl_injects)
        g2, r2, k2 = internal_thread_code(forever, graph)
        global_src = g1 + g2
        run_src = "void run_threads() {\n" + r1 + r2 + "}\n"
        kill_src = "void kill_threads() {\n" + k1 + k2 + "}\n"

    else:
        run_src = "void run_threads() { }\n"
        kill_src = "void kill_threads() { }\n"

        g1, r1, k1 = inject_thread_code(spec_injects)
        g2, r2, k2 = internal_thread_code([x for x in forever if re.match('_spec', x)], graph)
        global_src = g1 + g2
        run_src += "void spec_run_threads() {\n" + r1 + r2 + "}\n"
        kill_src += "void spec_kill_threads() {\n" + k1 + k2 + "}\n"

        g1, r1, k1 = inject_thread_code(impl_injects)
        g2, r2, k2 = internal_thread_code([x for x in forever if re.match('_impl', x)], graph)
        global_src += g1 + g2
        run_src += "void impl_run_threads() {\n" + r1 + r2 + "}\n"
        kill_src += "void impl_kill_threads() {\n" + k1 + k2 + "}\n"

    name = process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print global_src + run_src + kill_src


def generate_internal_triggers(graph, ext):
    for process in graph.processes:
        generate_internal_triggers_with_process(graph, process, ext)


def generate_inject_probe_code_with_process(graph, process, ext):
    injects = graph.inject_populates
    probes = graph.probe_compares
    src = ""
    if len(injects) or len(probes):
        inject_src = ""
        for state_instance in injects:
            inject = injects[state_instance]
            for key in inject.spec_instances:
                spec_instance = inject.spec_instances[key]
                if process in graph.state_instances[spec_instance].processes:
                    inject_src += generate_populate_state(inject, key)

        probe_src = ""
        for state_instance in probes:
            probe = probes[state_instance]
            for key in probe.spec_instances:
                spec_instance = probe.spec_instances[key]
                if process in graph.state_instances[spec_instance].processes:
                    probe_src += generate_compare_state(probe, key)

        src += "void init() {\n"
        src += "  init_memory_regions();\n"
        src += "  init_state_instances();\n"
        src += inject_src
        src += "}\n\n"

        src += "void finalize_and_check() {\n"
        src += probe_src
        src += "  finalize_memory_regions();\n"
        src += "  finalize_state_instances();\n"
        src += "}\n\n"
    else:
        src += "void init() {\n"
        src += "  init_memory_regions();\n"
        src += "  init_state_instances();\n"
        src += "}\n"
        src += "void finalize_and_check() {\n"
        src += "  finalize_memory_regions();\n"
        src += "  finalize_state_instances();\n"
        src += "}\n"

    name = process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src


def generate_inject_probe_code(graph, ext):
    for process in graph.processes:
        generate_inject_probe_code_with_process(graph, process, ext)


def generate_testing_code(graph, code, ext):
    src = "int main() {\n"
    src += "  init();\n"
    src += "  run_threads();\n"
    if code:
        src += "  " + code
    src += "  kill_threads();\n"
    src += "  finalize_and_check();\n"
    src += "\n  return 0;\n"
    src += "}\n"

    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def generate_populate_state(inject, key):
    # src = "  // %s: populate %s and %s\n" % \
    #       (inject.name, inject.spec_instances[key], inject.impl_instances[key])
    src = "  for(int i = 0; i < %d; i++) {\n" % inject.size
    src += "    %s temp = %s(i);\n" % (inject.type, inject.func)
    src += "    %s->data[i] = temp;\n" % inject.spec_instances[key]
    if key in inject.impl_instances:
        src += "    %s->data[i] = temp;\n" % inject.impl_instances[key]
    src += "  }\n"
    return src


def generate_compare_state(probe, key):
    if key not in probe.impl_instances:
        return ""
    spec = probe.spec_instances[key]
    impl = probe.impl_instances[key]
    # src = "  // %s: compare %s and %s\n" % \
    #       (probe.name, probe.spec_instances[key], probe.impl_instances[key])
    src = "  {0}({1}->p, {1}->data, {2}->p, {2}->data);\n".format(probe.func, spec, impl)
    return src


def generate_code(graph, ext, testing=None, include=None):
    """
    Display C code to stdout
    :param graph: data-flow graph
    """
    for process in graph.processes:
        name = process + ext
        os.system("rm " + name)

    generate_header(testing, graph.processes, ext)
    generate_include(include, graph.processes, ext)

    # Generate memory regions.
    generate_memory_regions(graph, ext)

    # Generate states.
    for state_name in graph.state_order:
        generate_state(graph.states[state_name], graph, ext)

    # Generate state instances.
    generate_state_instances(graph, ext)
    # for name in graph.state_instance_order:
    #     generate_state_instance(name, graph.state_instances[name], ext)

    # Generate functions to save join buffers.
    for instance in graph.instances.values():
        if instance.join_ports_same_thread:
            generate_join_save_function(instance.name, instance.join_ports_same_thread, instance, ext)

    # Generate functions to produce API return state
    return_funcs = []
    for api in graph.threads_API:
        if api.return_type and api.return_type not in return_funcs:
            return_funcs.append(api.return_type)
            generate_API_identity_macro(api, ext)

    # Generate signatures.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        generate_signature(instance, name, e.inports, ext)

    # Generate functions.
    for name in graph.instances:
        instance = graph.instances[name]
        e = instance.element
        state_rename = []
        for i in range(len(instance.state_args)):
            state_rename.append((e.state_params[i][1],instance.state_args[i]))
        element_to_function(instance, state_rename, graph, ext)

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


def generate_code_as_header(graph, testing, include=None, header='tmp.h'):
    generate_code(graph, ".h", testing, include)
    generate_inject_probe_code(graph, ".h")
    generate_internal_triggers(graph, ".h")


def generate_code_and_compile(graph, testing, include=None, depend=None, include_option=None):
    generate_code(graph, ".c", testing, include)
    generate_inject_probe_code(graph, ".c")
    generate_internal_triggers(graph, ".c")
    generate_testing_code(graph, testing, ".c")

    extra = ""
    if depend:
        for f in depend:
            extra += '%s.o ' % f
            cmd = 'gcc -O3 -msse4.1 -I %s -c %s.c -lrt' % (common.dpdk_include, f)
            status = os.system(cmd)
            if not status == 0:
                raise Exception("Compile error: " + cmd)

    for process in graph.processes:
        cmd = 'gcc -O3 -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % (common.dpdk_include, process, extra, process)
        status = os.system(cmd)
        if not status == 0:
            raise Exception("Compile error: " + cmd)


def generate_code_and_run(graph, testing, expect=None, include=None, depend=None, include_option=None):
    generate_code_and_compile(graph, testing, include, depend, include_option)

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
            ps = []
            p = subprocess.Popen(['./' + graph.master_process])
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


def compile_and_run(name, depend):
    extra = ""
    if depend:
        for f in depend:
            extra += '%s.o ' % f
            cmd = 'gcc -O3 -msse4.1 -I %s -c %s.c -lrt' % (common.dpdk_include, f)
            status = os.system(cmd)
            if not status == 0:
                raise Exception("Compile error: " + cmd)

    if isinstance(name, str):
        cmd = 'gcc -O3 -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % (common.dpdk_include, name, extra, name)
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
            cmd = 'gcc -O3 -msse4.1 -I %s -pthread %s.c %s -o %s -lrt' % (common.dpdk_include, f, extra, f)
            print cmd
            status = os.system(cmd)
            if not status == 0:
                raise Exception("Compile error: " + cmd)

        ps = []
        for f in name:
            p = subprocess.Popen(['./' + f])
            ps.append(p)

        time.sleep(3)
        for p in ps:
            p.kill()

