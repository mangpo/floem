from graph import AddressOf
import target

def assign_process_for_state_instance(g, process, st_inst_name):
    st_inst = g.state_instances[st_inst_name]
    state = st_inst.state
    st_inst.processes.add(process)
    state.processes.add(process)

    def inner(inits):
        if inits:
            for x in inits:
                if isinstance(x, AddressOf):
                    assign_process_for_state_instance(g, process, x.of)
                elif isinstance(x, str) and x in g.state_instances:
                    assign_process_for_state_instance(g, process, x)
                elif isinstance(x, list):
                    inner(x)

    inner(st_inst.init)


def annotate_process_info(g):
    if g.master_process:
        g.processes.add(g.master_process)

    for instance in g.instances.values():
        process = g.process_of_thread(instance.thread)
        device = g.device_of_thread(instance.thread)

        if device[0] == target.CAVIUM:
            process = device[0]

        g.process2device[process] = device[0]
        g.processes.add(process)
        g.devices.add(device[0])
        instance.process = process
        instance.device = device
        for st_inst_name in instance.state_args:
            assign_process_for_state_instance(g, process, st_inst_name)

    if g.master_process is None:
        g.master_process = [p for p in g.processes][0]

    for api in g.threads_API:
        process = g.process_of_thread(api.name)
        api.process = process

    for state_inst in g.state_instances.values():
        if len(state_inst.processes) > 1:
            pointer = state_inst.state.content.find('*')
            if pointer >= 0:
                if state_inst.buffer_for:
                    raise Exception("Element instance '%s' is receiving data from an instance in a different process.\n"
                                    % state_inst.name
                                    + "The data includes a pointer, which shouldn't be shared between multiple processes.\n"
                                    + "Consider inserting a smart queue between the sender instance and the receiver instance '%s'."
                                    % state_inst.buffer_for)
                else:
                    raise Exception("State instance '%s' is shared between multiple processes, but it contains pointer,\n"
                                    + "which shouldn't be shared between multiple processes."
                                    % state_inst.name)
