from codegen_thread import *
import types, os


def declare_state(name, state_instance, ext):
    state = state_instance.state
    src = "{0}* {1};\n".format(state.name, name)
    src_cavium = "CVMX_SHARED {0} _{1};\n".format(state.name, name)
    src_cavium += "CVMX_SHARED {0}* {1};\n".format(state.name, name)  # TODO: CVMX_SHARED or not?
    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            if process == target.CAVIUM:
                print src_cavium
            else:
                print src


def map_shared_state(name, state_instance, ext):
    state = state_instance.state
    src = "  {1} = ({0} *) shm_p;\n".format(state.name, name)
    src += "  shm_p = shm_p + sizeof({0});\n".format(state.name)

    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def allocate_state(name, state_instance, ext):
    state = state_instance.state
    src_cpu = "  {1} = ({0} *) malloc(sizeof({0}));\n".format(state.name, name)
    src_cavium = "  {0} = &_{0};\n".format(name)
    src = "  memset({0}, 0, sizeof({1}));\n".format(name, state.name)

    for process in state_instance.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            if process == target.CAVIUM:
                print src_cavium + src
            else:
                print src_cpu + src


def init_state(name, state_instance, state, master, ext):
    src = ""
    if state_instance.init or state.init:
        if state_instance.init:
            inits = state_instance.init
        else:
            inits = state.init
        src = init_pointer(state, inits, name)

    if len(state_instance.processes) <= 1:
        process = [x for x in state_instance.processes][0]
    else:
        process = master
    name = process + ext
    with open(name, 'a') as f, redirect_stdout(f):
        print src



def init_value(val):
    if isinstance(val, AddressOf):
        return '&' + val.of
    elif val is True:
        return "true"
    elif val is False:
        return "false"
    else:
        return val


def init_pointer(state, inits, name):
    if inits is None:
        return ""
    src = ""
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
                    if init[i]:
                        src += "  {0}->{1}[{2}] = {3};\n".format(name, array, i, init_value(init[i]))
        elif isinstance(init, types.LambdaType):
            src += "  %s;\n" % init("{0}->{1}".format(name, field))
        elif init:
            src += "  {0}->{1} = {2};\n".format(name, field, init_value(init))
    return src


# TODO: memory regions should be inclucded in there too.
def generate_state_instances_cpu_only(graph, ext, all_processes, shared):
    src = "size_t shm_size = 0;\n"
    src += "void *shm;\n"
    src_cpu = src + "void init_state_instances(char *argv[]) {\n"
    src_cavium = src + "void init_state_instances() {\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            if graph.process2device[process] == target.CPU:
                print src_cpu
            else:
                print src_cavium

    # Create shared memory
    if len(all_processes) > 1:
        # Check processes
        assert (graph.master_process in graph.processes), "Please specify a master process using master_process(name)."

        shared_src = ""
        for name in shared:
            inst = graph.state_instances[name]
            shared_src += "shm_size += sizeof(%s);\n" % inst.state.name
        master_src = 'shm = (uintptr_t) util_create_shmsiszed("SHARED", shm_size);\n'
        master_src += 'uintptr_t shm_p = (uintptr_t) shm;'
        slave_src = 'shm = (uintptr_t) util_map_shm("SHARED", shm_size);\n'
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
        init_state(name, inst, graph.states[inst.state.name], graph.master_process, ext)

    src = "}\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src

    # Finalize states
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


def generate_state_instances_cpu_cavium(graph, ext, all_processes, shared):
    if len(shared) > 0:
        # Kernel code
        os.system('rm uio_size.c')
        process = [p for p in all_processes if not (p == target.CAVIUM)][0]
        kernal_src = '#include "%s.h"\n' % process
        kernal_src += 'size_t get_shared_size() {\n'
        kernal_src += '  size_t shm_size = 0;\n'
        for name in shared:
            inst = graph.state_instances[name]
            kernal_src += '  shm_size += sizeof(%s);\n' % inst.state.name
        kernal_src += '  return shm_size;\n}\n'

        kernal_src += r'''
int main() {
  FILE *f = fopen("uio_simple.h", "w");
  fprintf(f, "#define SIZE %ld\n", get_shared_size());

  fclose(f);
  return 0;
}
        '''

        with open('uio_size.c', 'a') as f, redirect_stdout(f):
            print kernal_src

    src_cpu = "void init_state_instances(char *argv[]) {\n"
    src_cavium = "void init_state_instances() {\n"

    # Create shared memory
    if len(shared) > 0:
        # Check processes
        assert (graph.master_process in graph.processes), "Please specify a master process using master_process(name)."

        src_cpu += '  uintptr_t shm_p = (uintptr_t) util_map_dma();\n'
        src_cpu += '  uintptr_t shm_start = shm_p;\n'
        src_cavium += '  uintptr_t shm_p = STATIC_ADDRESS_HERE;\n'

    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            if graph.process2device[process] == target.CPU:
                print src_cpu
            else:
                print src_cavium

    # Initialize states
    for name in graph.state_instance_order:
        inst = graph.state_instances[name]
        if name in shared:
            map_shared_state(name, inst, ext)
        else:
            allocate_state(name, inst, ext)

    src_cpu = '  memset((void *) shm_start, 0, shm_p - shm_start);\n'
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            if graph.process2device[process] == target.CPU:
                print src_cpu

    for name in graph.state_instance_order:
        inst = graph.state_instances[name]
        init_state(name, inst, graph.states[inst.state.name], graph.master_process, ext)

    src = "}\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src

    # Finalize states
    src = "void finalize_state_instances() {}\n"
    for process in graph.processes:
        name = process + ext
        with open(name, 'a') as f, redirect_stdout(f):
            print src


def get_shared_states(graph):
    # Collect shared memory
    shared = set()
    all_processes = set()
    for name in graph.state_instance_order:
        inst = graph.state_instances[name]
        if len(inst.processes) > 1:
            # size = inst.state.size  # TODO
            # shared[name] = size
            # total_size += size
            shared.add(name)
            all_processes = all_processes.union(inst.processes)

    all_processes = [x for x in all_processes]

    return shared, all_processes


def generate_state_instances(graph, ext):
    # Declare states
    for name in graph.state_instance_order:
        declare_state(name, graph.state_instances[name], ext)

    # Collect shared memory
    shared , all_processes = get_shared_states(graph)
    if target.CAVIUM in graph.processes:
        generate_state_instances_cpu_cavium(graph, ext, all_processes, shared)
    else:
        generate_state_instances_cpu_only(graph, ext, all_processes, shared)
