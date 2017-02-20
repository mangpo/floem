from program import *
import compiler
import desugaring
import inspect

scope = [[]]
stack = []
fresh_id = 0

class PortCollect:
    def __init__(self):
        self.element_instance = None
        self.port = None


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name


def create_element(ele_name, inports, outports, code, local_state=None, state_params=[]):
    e = Element(ele_name, inports, outports, code, local_state, state_params)
    scope[-1].append(e)

    def create_instance(inst_name=None, args=[]):
        global fresh_id
        if inst_name is None:
            inst_name = ele_name + str(fresh_id)
            fresh_id += 1
        else:
            assert isinstance(inst_name, str), \
                "Name of element instance should be string. '%s' is given." % str(inst_name)
        inst_name = get_node_name(inst_name)
        instance = ElementInstance(ele_name, inst_name, args)
        scope[-1].append(instance)

        def connect(*ports):
            """
            :param ports: a list of (element_instance, out_port)
            :return:
            """
            assert len(ports) == len(e.inports), ("Instance of element '%s' requires %d inputs, %d inputs are given."
                                                  % (ele_name, len(e.inports), len(ports)))
            for i in range(len(e.inports)):
                from_port = ports[i]  # (element_instance, out_port)
                to_port = e.inports[i]  # Port

                if isinstance(from_port, PortCollect):
                    from_port.element_instance = inst_name
                    from_port.port = to_port.name
                elif from_port:
                    c = Connect(from_port[0], inst_name, from_port[1], to_port.name)
                    scope[-1].append(c)

            l = len(e.outports)
            if l == 0:
                return None
            elif l == 1:
                return (inst_name, e.outports[0].name)
            else:
                return tuple([(inst_name, port.name) for port in e.outports])
        # end connect
        return connect
    # end create_instance
    return create_instance


def create_composite(composite_name, program):
    assert callable(program), "The argument to create_composite must be lambda."
    args = inspect.getargspec(program).args
    n_args = len(args)
    fake_ports = [PortCollect() for i in range(n_args)]

    def create_instance(inst_name=None):
        if inst_name is None:
            inst_name = composite_name + str(fresh_id)
            fresh_id += 1
        else:
            assert isinstance(inst_name, str), \
                "Name of element instance should be string. '%s' is given." % str(inst_name)

        inst_name = get_node_name(inst_name)
        global stack
        stack.append(inst_name)
        outs = program(*fake_ports)
        stack = stack[:-1]

        def connect(*ports):
            assert len(ports) == n_args, ("Instance of composite '%s' requires %d inputs, %d inputs are given."
                                          % (composite_name, n_args, len(ports)))
            for i in range(n_args):
                from_port = ports[i]
                to_port = fake_ports[i]

                if isinstance(from_port, PortCollect):
                    from_port.element_instance = to_port.element_instance
                    from_port.port = to_port.port
                elif from_port:
                    c = Connect(from_port[0], to_port.element_instance, from_port[1], to_port.port)
                    scope[-1].append(c)
            return outs
        # end connect

        return connect
    # end create_instance

    return create_instance

def create_state(st_name, content, init=None):
    s = State(st_name, content, init)
    scope[-1].append(s)

    def create_instance(inst_name=None, init=False):
        global fresh_id
        if inst_name is None:
            inst_name = st_name + str(fresh_id)
            fresh_id += 1
        else:
            assert isinstance(inst_name, str), \
                "Name of state instance should be string. '%s' is given." % str(inst_name)

        inst_name = get_node_name(inst_name)
        instance = StateInstance(st_name, inst_name, init)
        scope[-1].append(instance)
        return inst_name

    return create_instance


class Compiler:
    def __init__(self):
        self.resource = True
        self.triggers = None

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

    def generate_graph(self):
        assert len(scope) == 1, "Compile error: there are multiple scopes remained."
        p = desugaring.desugar(Program(*scope[0]))
        g = compiler.generate_graph(p, self.resource)
        return g

    def generate_code(self):
        compiler.generate_code(self.generate_graph(), self.testing, self.include, self.triggers)

    def generate_code_with_test(self):
        compiler.generate_code_with_test(self.generate_graph(), self.testing, self.include, self.triggers)

    def generate_code_and_run(self, expect=None):
        compiler.generate_code_and_run(self.generate_graph(), self.testing, expect,
                                       self.include, self.depend, self.triggers)

    def generate_code_as_header(self, header='tmp.h'):
        compiler.generate_code_as_header(self.generate_graph(), self.testing, self.include, self.triggers, header)

    def compile_and_run(self, name):
        compiler.compile_and_run(name, self.depend)