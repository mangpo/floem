from graph import AddressOf


def assign_process_for_state_instance(g, process, st_inst_name):
    st_inst = g.state_instances[st_inst_name]
    state = st_inst.state
    st_inst.processes.add(process)
    state.processes.add(process)

    if isinstance(st_inst.init, list):
        for x in st_inst.init:
            if isinstance(x, AddressOf):
                assign_process_for_state_instance(g, process, x.of)
            elif isinstance(x, str) and x in g.state_instances:
                assign_process_for_state_instance(g, process, x)


def annotate_process_info(g):
    for instance in g.instances.values():
        process = g.process_of_thread(instance.thread)

        g.processes.add(process)
        instance.process = process
        for st_inst_name in instance.state_args:
            assign_process_for_state_instance(g, process, st_inst_name)

    for api in g.threads_API:
        process = g.process_of_thread(api.name)
        api.process = process
