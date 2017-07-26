import re


def nonempty_to_empty_port_pass(g):
    vis = set()
    for instance in g.instances.values():
        for port in instance.element.inports:
            if len(port.argtypes) == 0 and port.name in instance.input2ele:
                for prev_name, prev_portname in instance.input2ele[port.name]:
                    prev_inst = g.instances[prev_name]
                    prev_port = [port for port in prev_inst.element.outports if port.name == prev_portname][0]
                    if len(prev_port.argtypes) > 0:
                        element = prev_inst.element

                        if prev_name + "_empty" in vis:
                            new_element = element
                        else:
                            new_element = element.clone(prev_name + "_empty")
                            vis.add(prev_name + "_empty")
                            prev_inst.element = new_element
                            g.addElement(new_element)

                        prev_port = [port for port in new_element.outports if port.name == prev_portname][0]
                        prev_port.argtypes = []
                        new_element.reassign_output_values(prev_portname, '')