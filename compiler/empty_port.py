import re

def nonempty_to_empty_port_pass(g):
    vis = set()
    for instance in g.instances.values():
        for port in instance.element.inports:
            if len(port.argtypes) == 0:
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
                        if new_element.output_fire == "all":
                            new_element.output_code[prev_portname] = prev_portname + "()"
                        elif new_element.output_fire == "multi":
                            src = new_element.code
                            m = re.search('[^a-zA-Z0-9_](' + prev_portname + '[ ]*\([^;];)', src)
                            while m:
                                src = src[:m.start(1)] + prev_portname + "();" + src[m.end(1):]
                                m = re.search('[^a-zA-Z0-9_](' + prev_portname + '[ ]*\([^;];)', src)
                            new_element.code = src
                        else:
                            cases_exprs = new_element.output_code
                            for i in range(len(cases_exprs)):
                                expr = cases_exprs[i][1]
                                m = re.search(prev_portname + '[ ]*\(', expr)
                                if m:
                                    cases_exprs[i] = (cases_exprs[i][0], prev_portname + "()")

