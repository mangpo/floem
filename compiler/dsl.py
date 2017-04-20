from program import *
import compiler
import desugaring
import inspect

# Global variables for constructing a program.
scope = [[]]
stack = []
state_mapping = {}
fresh_id = 0


def reset():
    global scope, stack, state_mapping, fresh_id
    scope = [[]]
    stack = []
    state_mapping = {}
    fresh_id = 0


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name


class Thread:
    def __init__(self, name):
        self.name = name

    def run(self, *instances):
        for i in range(len(instances)):
            instance = instances[i]
            if isinstance(instance, ElementInstance):
                scope[-1].append(ResourceMap(self.name, instance.name))
            elif isinstance(instance, CompositeInstance):
                if instance.impl_instances_names:
                    scope[-1].append(Spec([ResourceMap(self.name, x) for x in instance.spec_instances_names]))
                    scope[-1].append(Impl([ResourceMap(self.name, x) for x in instance.impl_instances_names]))
                else:
                    for name in instance.spec_instances_names:
                        scope[-1].append(ResourceMap(self.name, name))
            elif isinstance(instance, SpecImplInstance):
                scope[-1].append(Spec([ResourceMap(self.name, x) for x in instance.spec_instances_names]))
                scope[-1].append(Impl([ResourceMap(self.name, x) for x in instance.impl_instances_names]))
            else:
                raise Exception("Thread.run unimplemented for '%s'" % instance)

    def run_order(self, *instances):
        self.run(*instances)
        for i in range(len(instances)-1):
            scope[-1].append(ResourceOrder(instances[i].name, instances[i+1].name))


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


class Process():
    def __init__(self, name, threads):
        self.name = name
        for t in threads:
            scope[-1].append(ProcessMap(name, t.name))


class CPU_process(Process):
    def __init__(self, name, *threads):
        Process.__init__(self, name, threads)


class ElementInstance:
    def __init__(self, name, instance, connect):
        self.name = name
        self.instance = instance
        self.connect = connect

    def __call__(self, *args, **kwargs):
        return self.connect(*args)


class CompositeInstance:
    def __init__(self, connect, spec_instances_names, impl_instances_names, roots, inputs, outputs, scope):
        self.connect = connect
        self.spec_instances_names = spec_instances_names
        self.impl_instances_names = impl_instances_names
        self.roots = roots
        self.inputs = inputs
        self.outputs = outputs
        self.scope = scope

    def __call__(self, *args):
        return self.connect(*args)


class SpecImplInstance:
    def __init__(self, connect, spec_instances_names, impl_instances_names):
        self.connect = connect
        self.spec_instances_names = spec_instances_names
        self.impl_instances_names = impl_instances_names

    def __call__(self, *args):
        return self.connect(*args)

class InputPortCollect:
    """
    An object of this class is used for collecting the element instances and ports that connect to the inputs of
    a composite or spec/impl composite.

    If the composite doesn't contain spec/impl composites, then self.impl* are not used.

    __call__ is for collecting thread bindings.
    """

    def __init__(self):
        self.instance = []
        self.port = []
        self.port_argtypes = []
        self.thread_run = None
        self.thread_args = None
        self.thread_order = None

        self.impl_instance = []
        self.impl_port = []
        self.impl_port_argtypes = []
        self.impl_thread_run = None
        self.impl_thread_args = None
        self.impl_thread_order = None

    def run(self, *args):
        self.thread_run = args

    def run_order(self, *args):
        self.thread_order = args

    def copy_to_spec(self, other):
        self.instance += other.instance
        self.port += other.port
        self.port_argtypes += other.impl_port_argtypes
        self.thread_run = other.thread_run
        self.thread_args = other.thread_args
        self.thread_order = other.thread_order

    def copy_to_impl(self, other):
        self.impl_instance += other.instance
        self.impl_port += other.port
        self.impl_port_argtypes += other.port_argtypes
        self.impl_thread_run = other.thread_run
        self.impl_thread_args = other.thread_args
        self.impl_thread_order = other.thread_order

    def copy_to_impl_from_impl(self, other):
        self.impl_instance += other.impl_instance
        self.impl_port += other.impl_port
        self.impl_port_argtypes += other.impl_port_argtypes
        self.impl_thread_run = other.impl_thread_run
        self.impl_thread_args = other.impl_thread_args
        self.impl_thread_order = other.impl_thread_order

    def has_impl(self):
        return self.impl_thread_run or self.impl_thread_order

    def spec_thread(self, t):
        if self.thread_run:
            t.run(*self.thread_run)
        if self.thread_order:
            t.run_order(*self.thread_order)

    def impl_thread(self, t):
        if self.impl_thread_run:
            t.run(*self.impl_thread_run)
        if self.impl_thread_order:
            t.run_order(*self.impl_thread_order)

    def __call__(self, *args):
        self.thread_args = args

    def get(self, field):
        raise Exception("Cannot extract field '%s' from an input to a composite because the type is unknown." % field)


class OutputPortCollect:
    """
    An object of this class is used for collecting the element instance and ports that connect to the outputs of
    a spec/impl or spec/impl composite.

    If the composite doesn't contain spec/impl composites, then self.impl* are not used.
    """

    def __init__(self, instance, port, port_argtypes, impl_instance=None, impl_port=None, impl_port_argtypes=None):
        assert isinstance(instance, str), "OutputPortCollect init"
        self.instance = instance
        self.port = port
        self.port_argtypes = port_argtypes

        self.impl_instance = impl_instance
        self.impl_port = impl_port
        self.impl_port_argtypes = impl_port_argtypes

        if impl_port_argtypes:
            assert port_argtypes == impl_port_argtypes, \
                ("Output port types of spec and impl must be the same. Spec output: %s. Impl output: %s."
                 % (port_argtypes, impl_port_argtypes))

    def get(self, field):
        assert len(self.port_argtypes) == 1, \
            ("Cannot extract field '%s' from port '%s' of instance '%s' because port '%s' contain multiple pieces of values."
             % (field, self.port, self.instance, self.port))

        field_list = field.replace('->', '.').split('.')

        first_t = self.port_argtypes[0]
        last_t = self.port_argtypes[0]
        content = "x"
        for f in field_list:
            if last_t[-1] == "*":
                mapping = state_mapping[last_t[:-1]]
                content = "extract*(%s, %s, %s)" % (content, last_t[:-1], f)
            else:
                mapping = state_mapping[last_t]
                content = "extract(%s, %s, %s)" % (content, last_t, f)
            last_t = mapping[f][0]

        inst_name = "extract_%s_%s_%s" % (self.instance, self.port, field.replace('.', '_').replace('->', '_'))
        inst = create_element_instance(inst_name, [Port("in", [first_t])], [Port("out", [last_t])],
                                       "%s x = in(); output { out(%s); }" % (first_t, content))
        out = inst(self)
        return out


def create_element(ele_name, inports, outports, code, local_state=None, state_params=[]):
    e = Element(ele_name, inports, outports, sanitize_variable_length(code), local_state, state_params)
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
                    from_port.instance.append(inst_name)
                    from_port.port.append(to_port.name)
                    from_port.port_argtypes.append(to_port.argtypes)
                elif isinstance(from_port, OutputPortCollect):
                    # OutputPortCollect can have both spec and impl.
                    if from_port.impl_instance:
                        c = Connect(from_port.instance, inst_name, from_port.port, to_port.name)
                        scope[-1].append(Spec([c]))
                        c = Connect(from_port.impl_instance, inst_name, from_port.impl_port, to_port.name)
                        scope[-1].append(Impl([c]))
                    else:
                        c = Connect(from_port.instance, inst_name, from_port.port, to_port.name)
                        scope[-1].append(c)
                elif from_port is None:
                    pass
                elif isinstance(from_port, tuple) and isinstance(from_port[0], OutputPortCollect):
                    raise Exception("Attempt to connect '%s'\nto iput port '%s' of element instance '%s'.\nCannot connect multiple output ports to one input port."
                                    % (from_port, to_port, inst_name))
                else:
                    raise Exception("Attempt to connect an unknown item %s to element instance '%s'."
                                    % (from_port, inst_name))

            l = len(e.outports)
            if l == 0:
                return None
            elif l == 1:
                return OutputPortCollect(inst_name, e.outports[0].name, e.outports[0].argtypes)
            else:
                return tuple([OutputPortCollect(inst_name, port.name, port.argtypes) for port in e.outports])
        # end connect
        return ElementInstance(inst_name, instance, connect)
    # end create_instance
    return create_instance


def create_element_instance(inst_name, inports, outports, code, local_state=None, state_params=[]):
    ele_name = "_element_" + inst_name
    ele = create_element(ele_name, inports, outports, code, local_state, state_params)
    return ele(inst_name)


def check_no_spec_impl(name, my_scope):
    for e in my_scope:
        if isinstance(e, Spec) or isinstance(e, Impl):
            raise Exception("API or internal trigger '%s' cannot wrap around spec and impl." % name)


def has_spec_impl(my_scope):
    for e in my_scope:
        if isinstance(e, Spec):
            return True
        elif isinstance(e, Impl):
            return True
    return False


def extract_instances_names(my_scope, inputs, outputs, spec=True):
    names = set()
    for e in my_scope:
        if isinstance(e, compiler.ElementInstance):
            names.add(e.name)
        elif isinstance(e, compiler.Connect):
            names.add(e.ele1)
            names.add(e.ele2)
        elif isinstance(e, Spec) and spec:
            additional = extract_instances_names(e.statements, [], None, spec)
            names = names.union(additional)
        elif isinstance(e, Impl) and not spec:
            additional = extract_instances_names(e.statements, [], None, spec)
            names = names.union(additional)

    for input in inputs:
        if spec:
            for instance in input.instance:
                names.add(instance)
        else:
            for instance in input.impl_instance:
                names.add(instance)

    if isinstance(outputs, tuple):
        for output in outputs:
            if isinstance(output, OutputPortCollect):
                if spec:
                    names.add(output.instance)
                else:
                    names.add(output.impl_instance)
            elif isinstance(output, InputPortCollect):
                if spec:
                    for inst in output.instance:
                        names.add(inst)
                else:
                    for inst in output.impl_instance:
                        names.add(inst)
    elif isinstance(outputs, OutputPortCollect):
        if spec:
            names.add(outputs.instance)
        else:
            names.add(outputs.impl_instance)
    elif isinstance(outputs, InputPortCollect):
        if spec:
            for inst in outputs.instance:
                names.add(inst)
        else:
            for inst in outputs.impl_instance:
                names.add(inst)
    return names


def extract_roots(my_scope, inputs, outputs):
    froms = set()
    tos = set()
    for e in my_scope:
        if isinstance(e, compiler.Connect):
            froms.add(e.ele1)
            tos.add(e.ele2)
        elif isinstance(e, compiler.ElementInstance):
            froms.add(e.name)

    for input in inputs:
        for instance in input.instance:
            froms.add(instance)

    if isinstance(outputs, tuple):
        for output in outputs:
            if isinstance(output, OutputPortCollect):
                froms.add(output.instance)
            elif isinstance(output, InputPortCollect):
                for inst in output.instance:
                    froms.add(inst)
    elif isinstance(outputs, OutputPortCollect):
        froms.add(outputs.instance)
    elif isinstance(outputs, InputPortCollect):
        for inst in outputs.instance:
            froms.add(inst)
    return froms.difference(tos)


def check_composite_inputs(name, inputs):
    for input in inputs:
        if len(input.port_argtypes) > 1:
            ref = input.port_argtypes[0]
            for i in range(1, len(input.port_argtypes)):
                assert input.port_argtypes[i] == ref, \
                    ("Input %d of composite '%s' is used in different places that expect different data types."
                     % (i, name))


def check_composite_outputs(name, outputs):
    if isinstance(outputs, InputPortCollect):
        raise Exception("Composite '%s' should not connect an input to an output directly." % name)
    elif isinstance(outputs, OutputPortCollect):
        pass
    elif isinstance(outputs, tuple):
        for o in outputs:
            if isinstance(o, InputPortCollect):
                raise Exception("Composite '%s' should not connect an input to an output directly." % name)
            elif isinstance(o, OutputPortCollect):
                pass
            else:
                raise Exception("Unknown output item at composite '%s'." % name)


def create_composite(composite_name, program):
    assert callable(program), "The second argument to create_composite must be lambda."
    args = inspect.getargspec(program).args
    n_args = len(args)

    def create_instance(inst_name=None):
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

        check_composite_outputs(inst_name, outs)
        check_composite_inputs(inst_name, fake_ports)
        spec_impl = has_spec_impl(my_scope)
        if spec_impl:
            spec_instances_names = extract_instances_names(my_scope, fake_ports, outs, spec=True)
            impl_instances_names = extract_instances_names(my_scope, fake_ports, outs, spec=False)
        else:
            spec_instances_names = extract_instances_names(my_scope, fake_ports, outs)
            impl_instances_names = None
        roots = extract_roots(my_scope, fake_ports, outs)

        def connect(*ports):
            for i in range(len(ports)):
                from_port = ports[i]
                to_port = fake_ports[i]

                if isinstance(from_port, InputPortCollect):
                    from_port.copy_to_spec(to_port)
                    from_port.copy_to_impl_from_impl(to_port)
                elif isinstance(from_port, Thread):
                    if to_port.has_impl():
                        global scope
                        scope.append([])
                        to_port.spec_thread(from_port)
                        this_scope = scope[-1]
                        scope = scope[:-1]
                        scope[-1].append(Spec(this_scope))

                        scope.append([])
                        to_port.impl_thread(from_port)
                        this_scope = scope[-1]
                        scope = scope[:-1]
                        scope[-1].append(Spec(this_scope))
                    else:
                        to_port.spec_thread(from_port)

                elif callable(from_port):
                    if to_port.thread_args:
                        from_port(*to_port.thread_args)
                    if to_port.impl_thread_args:
                        from_port(*to_port.impl_thread_args)
                elif isinstance(from_port, OutputPortCollect):
                    if from_port.impl_instance:
                        # from_port contains both spec and impl
                        for i in range(len(to_port.instance)):
                            c = Connect(from_port.instance, to_port.instance[i], from_port.port, to_port.port[i])
                            scope[-1].append(Spec([c]))
                        if len(to_port.impl_instance) > 0:
                            for i in range(len(to_port.impl_instance)):
                                c = Connect(from_port.impl_instance, to_port.impl_instance[i],
                                            from_port.impl_port, to_port.impl_port[i])
                                scope[-1].append(Impl([c]))
                        else:
                            for i in range(len(to_port.instance)):
                                c = Connect(from_port.impl_instance, to_port.instance[i],
                                            from_port.impl_port, to_port.port[i])
                                scope[-1].append(Impl([c]))
                    else:
                        # from_port contains only one version.
                        if len(to_port.impl_instance) > 0:
                            for i in range(len(to_port.instance)):
                                c = Connect(from_port.instance, to_port.instance[i], from_port.port, to_port.port[i])
                                scope[-1].append(Spec([c]))
                            for i in range(len(to_port.impl_instance)):
                                c = Connect(from_port.instance, to_port.impl_instance[i],
                                            from_port.port, to_port.impl_port[i])
                                scope[-1].append(Impl([c]))
                        else:
                            for i in range(len(to_port.instance)):
                                c = Connect(from_port.instance, to_port.instance[i], from_port.port, to_port.port[i])
                                scope[-1].append(c)
                elif from_port is None:
                    pass
                else:
                    raise Exception("Unknown composite connection %s" % from_port)
            return outs
        # end connect

        return CompositeInstance(connect, spec_instances_names, impl_instances_names, roots, fake_ports, outs, my_scope)
    # end create_instance

    return create_instance


def create_composite_instance(inst_name, program):
    composite_name = "composite_" + inst_name
    compo = create_composite(composite_name, program)
    return compo(inst_name)


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


def thread_common(name, f, input, output):
    compo = create_composite_instance("composite_" + name, f)
    check_no_spec_impl(name, compo.scope)
    input_types = []
    if input and len(compo.inputs) > 0:
        for input in compo.inputs:
            input_types += input.port_argtypes[0]

    output_type = None
    if output:
        if compo.outputs is None:
            output_type = None
        elif isinstance(compo.outputs, OutputPortCollect):
            assert len(compo.outputs.port_argtypes) == 1, \
                ("API '%s' can return no more than one value. Currently the return port has %d return values." %
                 (name, len(compo.outputs.port_argtypes)))
            output_type = compo.outputs.port_argtypes[0]
        else:
            raise Exception("API '%s' can return no more than one value. Currently it has %d return values."
                            % (name, len(compo.outputs)))

    # assert len(compo.roots) == 1, \
    #     ("API '%s' must have exactly one starting element, but currently these are starting elements: %s"
    #      % (name, compo.roots))

    return compo, input_types, output_type


def internal_trigger(name):
    def receptor(f):
        compo, input_types, output_type = thread_common(name, f, False, False)
        t = internal_thread(name)
        t.run(compo)
        return compo
    return receptor


def create_identity_multiports(ports_types):
    global fresh_id
    src_in = ""
    src_out = ""
    for i in range(len(ports_types)):
        types = ports_types[i]
        types_args = []
        args = []
        for j in range(len(types)):
            arg = "x%d_%d" % (i,j)
            types_args.append("%s %s" % (types[j], arg))
            args.append(arg)
        types_args = ','.join(types_args)
        args = ','.join(args)
        src_in += "(%s) = in%d();\n" % (types_args, i)
        src_out += "out%d(%s);\n" % (i, args)

    src = src_in
    src += "output {\n"
    src += src_out
    src += "}\n"
    name = "identiy%d" % fresh_id
    fresh_id += 1
    e = create_element(name,
                       [Port("in%d" % i, ports_types[i]) for i in range(len(ports_types))],
                       [Port("out%d" % i, ports_types[i]) for i in range(len(ports_types))],
                       src)
    return e


def API_common(name, f, input=True, output=True, default_return=None):
    compo, input_types, output_type = thread_common(name, f, input, output)
    if default_return:
        default_return = str(default_return)
    t = API_thread(name, input_types, output_type, default_return)
    t.run(compo)

    spec_starts = []
    impl_starts = []
    for input in compo.inputs:
        spec_starts += input.instance
        impl_starts += input.impl_instance

    if len(set(spec_starts)) > 1 or len(set(impl_starts)) > 1:
        # If there are multiple starting elements, insert an element as a starting element that forwards values
        # to proper elements.
        ports_types = []
        for input in compo.inputs:
            ports_types.append(input.port_argtypes[0])

        creator = create_identity_multiports(ports_types)
        e = creator()
        intermediates = e()
        if isinstance(intermediates, tuple):
            outputs = compo(*intermediates)
        else:
            outputs = compo(intermediates)
        #t.run_start(e)
        t.run(e)

        def new_compo(*args):
            e(*args)
            return outputs
        return new_compo
    else:
        #t.start([r for r in compo.roots][0])
        return compo


def API(name, default_return=None):
    def receptor(f):
        return API_common(name, f, default_return=default_return)
    return receptor


def API_implicit_inputs(name, default_return=None):
    def receptor(f):
        return API_common(name, f, input=False, default_return=default_return)
    return receptor


def API_implicit_outputs(name):
    def receptor(f):
        return API_common(name, f, output=False)
    return receptor


def API_implicit_inputs_outputs(name):
    def receptor(f):
        return API_common(name, f, input=False, output=False)
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

    check_composite_inputs(name, spec_fake_inports)
    check_composite_inputs(name, impl_fake_inports)
    check_composite_outputs(name, spec_outs)
    check_composite_outputs(name, impl_outs)
    spec_instances_names = extract_instances_names(spec_scope, spec_fake_inports, spec_outs)
    impl_instances_names = extract_instances_names(impl_scope, impl_fake_inports, impl_outs)

    outs = None
    if isinstance(spec_outs, tuple):
        assert (isinstance(impl_outs, tuple) and len(spec_outs) == len(impl_outs)), \
            ("The numbers of outputs of spec/impl of %s are different." % name)

        outs = []
        for i in range(len(spec_outs)):
            spec_instance = spec_outs[i].instance
            spec_port = spec_outs[i].port
            spec_port_argtypes = spec_outs[i].port_argtypes
            impl_instance = impl_outs[i].instance
            impl_port = impl_outs[i].port
            impl_port_argtypes = impl_outs[i].port_argtypes
            o = OutputPortCollect(spec_instance, spec_port, spec_port_argtypes,
                                  impl_instance, impl_port, impl_port_argtypes)
            outs.append(o)
    elif spec_outs:
        assert (isinstance(spec_outs, OutputPortCollect) and isinstance(impl_outs, OutputPortCollect)), \
            ("At spec/impl '%s', the output type of spec is %s, while output type of impl is %s."
             % (name, spec_outs, impl_outs))
        outs = OutputPortCollect(spec_outs.instance, spec_outs.port, spec_outs.port_argtypes,
                                 impl_outs.instance, impl_outs.port, impl_outs.port_argtypes)
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
                global scope
                scope.append([])
                spec_to_port.spec_thread(from_port)
                my_scope = scope[-1]
                scope = scope[:-1]
                scope[-1].append(Spec(my_scope))

                scope.append([])
                impl_to_port.spec_thread(from_port)
                my_scope = scope[-1]
                scope = scope[:-1]
                scope[-1].append(Impl(my_scope))

            elif callable(from_port):
                if spec_to_port.thread_args:
                    from_port(*spec_to_port.thread_args)
                if impl_to_port.thread_args:
                    from_port(*impl_to_port.thread_args)
            elif isinstance(from_port, OutputPortCollect):
                my_scope = []
                for i in range(len(spec_to_port.instance)):
                    c = Connect(from_port.instance, spec_to_port.instance[i], from_port.port, spec_to_port.port[i])
                    my_scope.append(c)
                scope[-1].append(Spec(my_scope))

                my_scope = []
                if from_port.impl_instance:
                    # from_port contains both spec and impl.
                    for i in range(len(impl_to_port.instance)):
                        c = Connect(from_port.impl_instance, impl_to_port.instance[i],
                                    from_port.impl_port, impl_to_port.port[i])
                        my_scope.append(c)
                else:
                    # from_port contains only one version.
                    for i in range(len(impl_to_port.instance)):
                        c = Connect(from_port.instance, impl_to_port.instance[i], from_port.port, impl_to_port.port[i])
                        my_scope.append(c)
                scope[-1].append(Impl(my_scope))

            elif from_port is None:
                pass
            else:
                raise Exception("Unknown spec/impl connection %s" % from_port)
        return outs
        # end connect

    return SpecImplInstance(connect, spec_instances_names, impl_instances_names)


def sanitize_variable_length(code):
    working = True
    while working:
        working = False
        m = re.search('extract([\*]?)\([ ]*([a-zA-Z0-9_.>\-]+)[ ]*,[ ]*([a-zA-Z0-9_]+)[ ]*,[ ]*([a-zA-Z0-9_]+)[ ]*\)', code)
        if m:
            pointer = m.group(1)
            var = m.group(2)
            state = m.group(3)
            field = m.group(4)

            assert state in state_mapping, \
                ("State '%s' is undefined. Cannot extract field for this state." % state)
            assert field in state_mapping[state], \
                ("Extract field error: state '%s' does not contain field '%s'." % (state, field))

            extract = state_mapping[state][field][1]
            if pointer == '*':
                extract = extract.format(var + '->')
            else:
                extract = extract.format(var + '.')

            code = code[:m.start(0)] + extract + code[m.end(0):]
            working = True
    return code


def get_state_mapping(content):
    """
    Handle state with variable-length fields.
    :param content: content of the original state
    :return: content , reorder, mapping
    content -- content for C struct
    reorder -- true if the order of the new content differs from the old content
    mapping -- mapping of field to the correct reference
    """
    fields = content.split(';')[:-1]  # discard the last one
    fixed_len_order = []
    variable_len_order = []
    fixed_len = {}
    variable_len = {}
    for field in fields:
        field = field.lstrip().rstrip()
        index = field.rfind(' ')
        t = field[:index].rstrip()
        var = field[index+1:]
        m = re.match('([^\[]+)\[([^\]]+)\]', var)  # only support one dimension
        if m:
            name = m.group(1)
            l = m.group(2)
            try:
                size = int(l)
                fixed_len[name] = (t + '*')
                fixed_len_order.append(name)
            except ValueError:
                assert l in fixed_len, ("The size of field '%s' should refer to previously defined field." % var)
                variable_len[name] = (t, l)
                variable_len_order.append(name)
        else:
            fixed_len[var] = t
            fixed_len_order.append(var)

    if len(variable_len) == 0:
        field_mapping = {}
        for var in fixed_len_order:
            t = fixed_len[var]
            field_mapping[var] = (t, "{0}%s" % var)
        return content, False, field_mapping
    elif len(variable_len_order) == 1:
        var_len_var = variable_len_order[0]
        var_t = variable_len[var_len_var][0]
        field_mapping = {}
        for var in fixed_len_order:
            t = fixed_len[var]
            field_mapping[var] = (t, "{0}%s" % var)
        field_mapping[var_len_var] = (var_t + '*', "{0}%s" % var_len_var)

        content = ""
        for var in fixed_len:
            content += "%s %s;\n" % (fixed_len[var], var)
        content += "%s %s[];\n" % (var_t, var_len_var)
        if variable_len_order[0] == var_len_var:
            return content, False, field_mapping
        else:
            return content, True, field_mapping
    else:
        content = ""
        for var in fixed_len_order:
            content += "%s %s;\n" % (fixed_len[var], var)
        content += "uint8_t _rest[];\n"

        # Create field mapping
        field_mapping = {}
        first_var = variable_len_order[0]
        t, prev_size = variable_len[first_var]
        pointer = "(%s*) {0}_rest" % t
        field_mapping[first_var] = (t + '*', pointer)

        for var in fixed_len_order:
            t = fixed_len[var]
            field_mapping[var] = (t, "{0}%s" % var)

        for var in variable_len_order[1:]:
            t, size = variable_len[var]
            pointer = "(%s*) (%s + {0}%s)" % (t, pointer, prev_size)
            prev_size = size
            field_mapping[var] = (t + '*', pointer)

        return content, True, field_mapping


def create_state(st_name, content, init=None):
    if isinstance(content, list):
        src = ""
        for t, var in content:
            src = "%s %s;\n" % (t, var)
        content = src

    content, reorder, mapping = get_state_mapping(content)
    assert st_name not in state_mapping, ("State '%s' is redefined." % st_name)
    state_mapping[st_name] = mapping

    if reorder and init:
        raise Exception("Cannot initialize state '%s' when there are more than one variable-length field." % st_name)

    s = State(st_name, content, init)
    scope[-1].append(s)

    def create_instance(inst_name=None, init=False):
        if reorder and init:
            raise Exception(
                "Cannot initialize state '%s' when there are more than one variable-length field." % st_name)

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


def create_state_instance_from(st_name, inst_name, init=None):
    inst_name = get_node_name(inst_name)
    instance = StateInstance(st_name, inst_name, init)
    scope[-1].append(instance)
    return inst_name


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
        self.remove_unused = True

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

        # Compiler option
        self.I = None

    def generate_graph(self):
        assert len(scope) == 1, "Compile error: there are multiple scopes remained."
        p1 = Program(*scope[0])
        p2 = desugaring.desugar(p1, self.desugar_mode)
        dp = desugaring.insert_fork(p2)
        g = compiler.generate_graph(dp, self.resource, self.remove_unused)
        return g

    def generate_code(self):
        compiler.generate_code(self.generate_graph(), self.testing, self.include)

    def generate_code_with_test(self):
        compiler.generate_code_with_test(self.generate_graph(), self.testing, self.include)

    def generate_code_and_run(self, expect=None):
        compiler.generate_code_and_run(self.generate_graph(), self.testing, expect, self.include, self.depend, self.I)

    def generate_code_and_compile(self):
        compiler.generate_code_and_compile(self.generate_graph(), self.testing, self.include, self.depend, self.I)

    def generate_code_as_header(self, header='tmp.h'):
        compiler.generate_code_as_header(self.generate_graph(), self.testing, self.include, header)

    def compile_and_run(self, name):
        compiler.compile_and_run(name, self.depend, self.I)