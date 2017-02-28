from program import *
import compiler
import desugaring
import inspect

# Global variables for constructing a program.
scope = [[]]
stack = []
fresh_id = 0


def reset():
    global scope, stack, fresh_id
    scope = [[]]
    stack = []
    fresh_id = 0


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name


class Thread:
    def __init__(self, name):
        self.name = name

    def start(self, instance):
        assert isinstance(instance, ElementInstance), \
            "Resource '%s' must start at an element instance not a composite instance."
        scope[-1].append(ResourceStart(self.name, instance.name))

    def run_start(self, *instances):
        self.run(*instances)
        self.start(instances[0])

    def run(self, *instances):
        for i in range(len(instances)):
            instance = instances[i]
            if isinstance(instance, ElementInstance):
                scope[-1].append(ResourceMap(self.name, instance.name))
            elif isinstance(instance, CompositeInstance):
                for name in instance.instances_names:
                    scope[-1].append(ResourceMap(self.name, name))


class API_thread(Thread):
    def __init__(self, name, call_types, return_types, default_val=None):
        Thread.__init__(self, name)
        api = APIFunction(name, call_types, return_types, default_val)
        scope[-1].insert(0, api)


class internal_thread(Thread):
    def __init__(self, name):
        name = get_node_name(name)
        Thread.__init__(self, name)
        trigger = InternalTrigger(name)
        scope[-1].insert(0, trigger)


class ElementInstance:
    def __init__(self, name, instance, connect):
        self.name = name
        self.instance = instance
        self.connect = connect

    def __call__(self, *args, **kwargs):
        return self.connect(*args)


class CompositeInstance:
    def __init__(self, connect, instances_names):
        self.connect = connect
        self.instances_names = instances_names

    def __call__(self, *args, **kwargs):
        return self.connect(*args)


class InputPortCollect:
    """
    An object of this class is used for collecting the element instances and ports that connect to the inputs of
    a composite or spec/impl composite.

    If the composite doesn't contain spec/impl composites, then self.impl* are not used.

    __call__ is for collecting thread bindings.
    """

    def __init__(self):
        self.instance = None
        self.port = None
        self.thread_run = None
        self.thread_start = None
        self.thread_args = None

        self.impl_instance = None
        self.impl_port = None
        self.impl_thread_run = None
        self.impl_thread_start = None
        self.impl_thread_args = None

    def start(self, e):
        self.thread_start = e

    def run(self, *args):
        self.thread_run = args

    def run_start(self, *args):
        self.run(*args)
        self.start(args[0])

    def copy_to_spec(self, other):
        self.instance = other.instance
        self.port = other.port
        self.thread_run = other.thread_run
        self.thread_start = other.thread_start
        self.thread_args = other.thread_args

    def copy_to_impl(self, other):
        self.impl_instance = other.instance
        self.impl_port = other.port
        self.impl_thread_run = other.thread_run
        self.impl_thread_start = other.thread_start
        self.impl_thread_args = other.thread_args

    def copy_to_impl_from_impl(self, other):
        self.impl_instance = other.impl_instance
        self.impl_port = other.impl_port
        self.impl_thread_run = other.impl_thread_run
        self.impl_thread_start = other.impl_thread_start
        self.impl_thread_args = other.impl_thread_args

    def spec_thread(self, t):
        if self.thread_run:
            t.run(*self.thread_run)
        if self.thread_start:
            t.start(self.thread_start)

    def impl_thread(self, t):
        if self.impl_thread_run:
            t.run(*self.impl_thread_run)
        if self.impl_thread_start:
            t.start(self.impl_thread_start)

    def __call__(self, *args):
        self.thread_args = args

class OutputPortCollect:
    """
    An object of this class is used for collecting the element instance and ports that connect to the outputs of
    a spec/impl or spec/impl composite.

    If the composite doesn't contain spec/impl composites, then self.impl* are not used.
    """

    def __init__(self, instance, port, impl_instance=None, impl_port=None):
        self.instance = instance
        self.port = port

        self.impl_instance = impl_instance
        self.impl_port = impl_port


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

                if isinstance(from_port, InputPortCollect):
                    # InputPortCollect only contains spec version because we evaluate the inner body of spec and impl
                    # separately.
                    from_port.instance = inst_name
                    from_port.port = to_port.name
                elif isinstance(from_port, OutputPortCollect):
                    # OutputPortCollect can have both spec and impl.
                    c = Connect(from_port.instance, inst_name, from_port.port, to_port.name)
                    if from_port.impl_instance:
                        scope[-1].append(Spec([c]))
                        c = Connect(from_port.impl_instance, inst_name, from_port.impl_port, to_port.name)
                        scope[-1].append(Impl([c]))
                    else:
                        scope[-1].append(c)
                elif from_port is None:
                    pass
                else:
                    raise Exception("Attempt to connect an unknown item %s to element instance '%s'."
                                    % (from_port, inst_name))

            l = len(e.outports)
            if l == 0:
                return None
            elif l == 1:
                return OutputPortCollect(inst_name, e.outports[0].name)
            else:
                return tuple([OutputPortCollect(inst_name, port.name) for port in e.outports])
        # end connect
        return ElementInstance(inst_name, instance, connect)
    # end create_instance
    return create_instance


def create_element_instance(inst_name, inports, outports, code, local_state=None, state_params=[]):
    ele_name = "_element_" + inst_name
    ele = create_element(ele_name, inports, outports, code, local_state, state_params)
    return ele(inst_name)


def extract_instances_names(my_scope):
    names = []
    for e in my_scope:
        if isinstance(e, compiler.ElementInstance):
            names.append(e.name)
    return names


def create_composite(composite_name, program):
    assert callable(program), "The second argument to create_composite must be lambda."
    args = inspect.getargspec(program).args
    n_args = len(args)

    def create_instance(inst_name=None, threads=[]):
        if inst_name is None:
            global fresh_id
            inst_name = composite_name + str(fresh_id)
            fresh_id += 1
        else:
            assert isinstance(inst_name, str), \
                "Name of element instance should be string. '%s' is given." % str(inst_name)

        fake_ports = [InputPortCollect() for i in range(n_args)]
        global stack, scope
        scope.append([])
        stack.append(inst_name)
        outs = program(*fake_ports)
        stack = stack[:-1]
        my_scope = scope[-1]
        scope = scope[:-1]
        scope[-1] = scope[-1] + my_scope

        instances_names = extract_instances_names(my_scope)

        def connect(*ports):
            # assert len(ports) == n_args, ("Instance of composite '%s' requires %d inputs, %d inputs are given."
            #                               % (composite_name, n_args, len(ports)))
            for i in range(len(ports)):
                from_port = ports[i]
                to_port = fake_ports[i]

                if isinstance(from_port, InputPortCollect):
                    from_port.copy_to_spec(to_port)
                    from_port.copy_to_impl_from_impl(to_port)
                elif isinstance(from_port, Thread):
                    to_port.spec_thread(from_port)
                    to_port.impl_thread(from_port)
                elif callable(from_port):
                    if to_port.thread_args:
                        from_port(*to_port.thread_args)
                    if to_port.impl_thread_args:
                        from_port(*to_port.impl_thread_args)
                elif isinstance(from_port, OutputPortCollect):
                    if from_port.impl_instance:
                        # from_port contains both spec and impl
                        c = Connect(from_port.instance, to_port.instance, from_port.port, to_port.port)
                        scope[-1].append(Spec([c]))
                        if to_port.impl_instance:
                            c = Connect(from_port.impl_instance, to_port.impl_instance,
                                        from_port.impl_port, to_port.impl_port)
                        else:
                            c = Connect(from_port.impl_instance, to_port.instance,
                                        from_port.impl_port, to_port.port)
                        scope[-1].append(Impl([c]))
                    else:
                        # from_port contains only one version.
                        c = Connect(from_port.instance, to_port.instance, from_port.port, to_port.port)
                        if to_port.impl_instance:
                            scope[-1].append(Spec([c]))
                            c = Connect(from_port.instance, to_port.impl_instance,
                                        from_port.port, to_port.impl_port)
                            scope[-1].append(Impl([c]))
                        else:
                            scope[-1].append(c)
                elif from_port is None:
                    pass
                else:
                    raise Exception("Unknown composite connection %s" % from_port)
            return outs
        # end connect

        return CompositeInstance(connect, instances_names)
    # end create_instance

    return create_instance


def create_composite_instance(inst_name, program):
    composite_name = "_composite_" + inst_name
    compo = create_composite(composite_name, program)
    return compo()


def composite_instance_at(name, t):
    def receptor(f):
        compo = create_composite_instance(name, f)
        t.run(compo)
        return compo
    return receptor


def composite_instance(name):
    def receptor(f):
        return create_composite_instance(name, f)
    return receptor


def create_spec_impl(name, spec_func, impl_func):
    """
    Create composite instance for spec and impl.
    :param name: name of this composite
    :param spec_func:
    :param impl_func:
    :return: composite instance
    """
    assert callable(spec_func), "The second argument to create_composite must be lambda."
    assert callable(impl_func), "The third argument to create_composite must be lambda."
    spec_args = inspect.getargspec(spec_func).args
    impl_args = inspect.getargspec(impl_func).args
    assert len(spec_args) == len(impl_args), "spec_func and impl_func take different numbers of arguments."
    n_args = len(spec_args)

    def create_instance(inst_name, program, fake_ports):
        global stack
        stack.append(inst_name)
        outs = program(*fake_ports)
        stack = stack[:-1]
        return outs

    global scope
    spec_fake_inports = [InputPortCollect() for i in range(n_args)]
    scope.append([])
    spec_outs = create_instance(name, spec_func, spec_fake_inports)
    spec_scope = scope[-1]
    scope = scope[:-1]
    scope[-1].append(Spec(spec_scope))

    impl_fake_inports = [InputPortCollect() for i in range(n_args)]
    scope.append([])
    impl_outs = create_instance(name, impl_func, impl_fake_inports)
    impl_scope = scope[-1]
    scope = scope[:-1]
    scope[-1].append(Impl(impl_scope))

    if isinstance(spec_outs, tuple):
        assert (isinstance(impl_outs, tuple) and len(spec_outs) == len(impl_outs)), \
            ("The numbers of outputs of spec/impl of %s are different." % name)

        outs = []
        for i in range(len(spec_outs)):
            spec_instance = spec_outs[i].instance
            spec_port = spec_outs[i].port
            impl_instance = impl_outs[i].instance
            impl_port = impl_outs[i].port
            o = OutputPortCollect(spec_instance, spec_port, impl_instance, impl_port)
            outs.append(o)
    elif spec_outs:
        assert (isinstance(spec_outs, OutputPortCollect) and isinstance(impl_outs, OutputPortCollect)), \
            ("At spec/impl '%s', the output type of spec is %s, while output type of impl is %s."
             % (name, spec_outs, impl_outs))
        spec_instance = spec_outs.instance
        spec_port = spec_outs.port
        impl_instance = impl_outs.instance
        impl_port = impl_outs.port
        outs = OutputPortCollect(spec_instance, spec_port, impl_instance, impl_port)
    else:
        assert (spec_outs is None and impl_outs is None), \
            ("At spec/impl '%s', the output type of spec is %s, while output type of impl is %s."
             % (name, spec_outs, impl_outs))
        outs = None

    def connect(*ports):
        for i in range(len(ports)):
            from_port = ports[i]
            spec_to_port = spec_fake_inports[i]
            impl_to_port = impl_fake_inports[i]

            if isinstance(from_port, InputPortCollect):
                from_port.copy_to_spec(spec_to_port)
                from_port.copy_to_impl(impl_to_port)
            elif isinstance(from_port, Thread):
                spec_to_port.spec_thread(from_port)
                impl_to_port.spec_thread(from_port)
            elif callable(from_port):
                if spec_to_port.thread_args:
                    from_port(*spec_to_port.thread_args)
                if impl_to_port.thread_args:
                    from_port(*impl_to_port.thread_args)
            elif isinstance(from_port, OutputPortCollect):
                c = Connect(from_port.instance, spec_to_port.instance, from_port.port, spec_to_port.port)
                spec_scope.append(c)
                if from_port.impl_instance:
                    # from_port contains both spec and impl.
                    c = Connect(from_port.impl_instance, impl_to_port.instance, from_port.impl_port, impl_to_port.port)
                    impl_scope.append(c)
                else:
                    # from_port contains only one version.
                    c = Connect(from_port.instance, impl_to_port.instance, from_port.port, impl_to_port.port)
                    impl_scope.append(c)
            elif from_port is None:
                pass
            else:
                raise Exception("Unknown spec/impl connection %s" % from_port)
        return outs
        # end connect

    return connect


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


def populte_state(name, st_inst_name, st_name, type, size, func):
    """
    Initialize inject state.
    :param name: inject element name
    :param st_inst_name: state instance name
    :param st_name: state name
    :param type: type of values to be generated
    :param size: number of values
    :param func: a name of a generator function.
    The function should take an integer argument indicating the ID of iteration.
    It should return a generated value.
    """
    scope[-1].insert(0, PopulateState(name, st_inst_name, st_name, type, size, func))


def compare_state(name, st_inst_name, st_name, type, size, func):
    """
    Compare the content stored in probe states of spec and impl.
    :param name: probe element name
    :param st_inst_name: state instance name
    :param st_name: state name
    :param type: type of values to be compared
    :param size: number of values
    :param func: a comparison function.
    The function should take (int spec_n, <type> *spec_data, int impl_n, <type> *impl_data).
    If incorrect, the function should exit with non-zero status.
    """
    scope[-1].insert(0, CompareState(name, st_inst_name, st_name, type, size, func))


class Compiler:
    def __init__(self):
        self.desugar_mode = "impl"
        self.resource = True
        self.triggers = None

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

    def generate_graph(self):
        assert len(scope) == 1, "Compile error: there are multiple scopes remained."
        p = Program(*scope[0])
        dp = desugaring.desugar(p, self.desugar_mode)
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