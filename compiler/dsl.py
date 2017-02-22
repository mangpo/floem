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
        self.thread_run_args = None

    def __call__(self, *args, **kwargs):
        self.thread_run_args = args


class Thread:
    def __init__(self, name):
        self.name = name

    def run_start(self, *instances):
        instances[0].assign_thread(self.name, True)
        for i in range(1, len(instances)):
            instance = instances[i]
            instance.assign_thread(self.name, False)

    def run(self, *instances):
        for i in range(len(instances)):
            instance = instances[i]
            instance.assign_thread(self.name, False)


class API_thread(Thread):
    def __init__(self, name, call_types, return_types, default_val=None):
        Thread.__init__(self, name)
        api = APIFunction2(name, call_types, return_types, default_val)
        scope[-1].insert(0, api)


class internal_thread(Thread):
    def __init__(self, name):
        Thread.__init__(self, name)
        trigger = InternalTrigger2(name)
        scope[-1].append(trigger)


class ElementInstance:
    def __init__(self, name, instance, connect):
        self.name = name
        self.instance = instance
        self.connect = connect

    def __call__(self, *args, **kwargs):
        return self.connect(*args)

    def assign_thread(self, thread, flag):
        self.instance.thread = thread
        self.instance.thread_flag = flag


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
        instance = compiler.ElementInstance(ele_name, inst_name, args)
        scope[-1].append(instance)

        def connect(*ports):
            """
            :param ports: a list of (element_instance, out_port)
            :return:
            """
            # assert len(ports) == len(e.inports), ("Instance of element '%s' requires %d inputs, %d inputs are given."
            #                                       % (ele_name, len(e.inports), len(ports)))
            for i in range(len(ports)):
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
        return ElementInstance(inst_name, instance, connect)
    # end create_instance
    return create_instance


def create_element_instance(inst_name, inports, outports, code, local_state=None, state_params=[]):
    ele_name = "_element_" + inst_name
    ele = create_element(ele_name, inports, outports, code, local_state, state_params)
    return ele(inst_name)


def create_composite(composite_name, program):
    assert callable(program), "The argument to create_composite must be lambda."
    args = inspect.getargspec(program).args
    n_args = len(args)
    fake_ports = [PortCollect() for i in range(n_args)]

    def create_instance(inst_name=None):
        if inst_name is None:
            global fresh_id
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
            # assert len(ports) == n_args, ("Instance of composite '%s' requires %d inputs, %d inputs are given."
            #                               % (composite_name, n_args, len(ports)))
            for i in range(len(ports)):
                from_port = ports[i]
                to_port = fake_ports[i]

                if callable(from_port):
                    from_port(*to_port.thread_run_args)
                elif isinstance(from_port, PortCollect):
                    from_port.element_instance = to_port.element_instance
                    from_port.port = to_port.port
                    from_port.thread_run_args = to_port.thread_run_args
                elif from_port:
                    c = Connect(from_port[0], to_port.element_instance, from_port[1], to_port.port)
                    scope[-1].append(c)
            return outs
        # end connect

        return connect
    # end create_instance

    return create_instance


def create_composite_instance(inst_name, program):
    composite_name = "_composite_" + inst_name
    compo = create_composite(composite_name, program)
    return compo()


def create_inject_instance(inst_name, type, size, func):
    instance = compiler.Inject(type, inst_name, size, func)
    scope[-1].append(instance)

    def connect():
        return (inst_name, "out")

    return ElementInstance(inst_name, instance, connect)


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


def create_state_instance(inst_name, content, init=None):
    st_name = "_state_" + inst_name
    state = create_state(st_name, content, init)
    return state(inst_name)


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
        p = Program(*scope[0])
        dp = desugaring.desugar(p)
        g = compiler.generate_graph(dp, self.resource)
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