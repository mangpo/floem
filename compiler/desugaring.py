from program import *
import re
import standard_elements


def insert_fork(x):
    new_x = clone_block(x)
    insert_fork_program(new_x)
    return new_x


def clone_block(x):
    if isinstance(x, Program):
        statements = [clone_block(s) for s in x.statements]
        return Program(*statements)
    elif isinstance(x, Spec):
        statements = [clone_block(s) for s in x.statements]
        return Spec(statements)
    elif isinstance(x, Impl):
        statements = [clone_block(s) for s in x.statements]
        return Impl(statements)
    elif isinstance(x, Composite):
        return Composite(x.name, clone_block(x.program))
    elif isinstance(x, Connect):
        return Connect(x.ele1, x.ele2, x.out1, x.in2)
    elif isinstance(x, ResourceOrder):
        return ResourceOrder(x.a, x.b)
    else:
        return x


def insert_fork_other(x, connect_map, element_map, instance_map, resource_map, resource_order):
    """
    Insert fork if an output port of an instance is connected more than one time.
    :param x: AST
    :param connect_map: a map from (inst_name, port_name) to a list of the corresponding Connect AST nodes
    :param env: a map from (inst_name, instance) and (ele_name, element)
    :return: result AST
    """
    if isinstance(x, Program) or isinstance(x, Spec) or isinstance(x, Impl):
        return insert_fork_program(x)
    elif isinstance(x, Composite):
        return insert_fork_program(x.program)
    elif isinstance(x, Connect):
        if (x.ele1, x.out1) not in connect_map:
            connect_map[(x.ele1, x.out1)] = []
            connect_map[(x.ele1, x.out1)].append(x)
            return False
        else:
            connect_map[(x.ele1, x.out1)].append(x)
            return True
    elif isinstance(x, Element):
        element_map[x.name] = x
    elif isinstance(x, ElementInstance):
        instance_map[x.name] = x
    elif isinstance(x, ResourceMap):
        resource_map[x.instance] = x.resource
    elif isinstance(x, ResourceOrder):
        resource_order[x.a] = x
    return False

fork_id = 0

def insert_fork_program(x):
    connect_map = {}
    resource_map = {}
    resource_order = {}
    element_map = {}
    instance_map = {}
    ret = False
    for st in x.statements:
        this_ret = insert_fork_other(st, connect_map, element_map, instance_map, resource_map, resource_order)
        ret = ret or this_ret
    if ret:
        for inst_name, port_name in connect_map:
            connects = connect_map[(inst_name, port_name)]
            if len(connects) > 1:
                ele_name = instance_map[inst_name].element
                element = element_map[ele_name]
                port = [port for port in element.outports if port.name == port_name][0]

                # Statements to insert into program
                global fork_id
                fork = standard_elements.Fork_multi_values(inst_name + "_" + port_name + "_fork" + str(fork_id),
                                                           len(connects), port.argtypes)
                fork_id += 1
                fork_inst = ElementInstance(fork.name, fork.name + "_inst")
                fork_connect = Connect(inst_name, fork_inst.name, port_name, "in")

                x.statements.insert(0, fork_inst)
                x.statements.insert(0, fork)
                x.statements.append(fork_connect)

                # Add ResourceMap for fork
                if inst_name in resource_map:
                    resource = ResourceMap(resource_map[inst_name], fork_inst.name)
                    x.statements.append(resource)

                # Adjust ResourceOrder
                if inst_name in resource_order:
                    resource_order[inst_name].a = fork_inst.name

                # Mutate Connect to connect to fork
                for i in range(len(connects)):
                    connects[i].ele1 = fork_inst.name
                    connects[i].out1 = "out" + str(i+1)
        return True
    return False



def desugar(x, mode="impl"):
    """
    :param x: program AST
    :param mode: "spec", "impl", "compare"
    :return: desugared AST
    """
    need = need_desugar(x)
    if not need:
        return x

    if mode == "compare":
        D = Desugar(True)
        spec = Composite("Spec", D.process(x))
        impl = Composite("Impl", Desugar(False).process(x))
        spec_instance = CompositeInstance("Spec", "spec")
        impl_instance = CompositeInstance("Impl", "impl")
        statements = []
        statements += D.populates
        statements += D.compares
        statements += [spec, impl, spec_instance, impl_instance]
        return Program(*statements)
    elif mode == "spec":
        D = Desugar(True)
        statements = D.process(x).statements
        statements = D.populates + [x for x in statements]
        return Program(*statements)
    elif mode == "impl":
        D = Desugar(False)
        statements = D.process(x).statements
        statements = D.populates + [x for x in statements]
        return Program(*statements)
    else:
        raise Exception("Unknown desugaring mode '%s'" % mode)


def need_desugar(x):
    if isinstance(x, Program):
        for st in x.statements:
            need = need_desugar(st)
            if need:
                return True
        return False
    elif isinstance(x, Composite):
        return need_desugar(x.program)
    elif isinstance(x, Spec):
        return True
    elif isinstance(x, Impl):
        return True
    elif isinstance(x, ElementInstance):
        index = x.name.find("[")
        return index >= 0
    elif isinstance(x, CompositeInstance):
        index = x.name.find("[")
        return index >= 0
    elif isinstance(x, StateInstance):
        index = x.name.find("[")
        return index >= 0


class Desugar:
    def __init__(self, spec):
        self.spec = spec
        self.env = {}

        self.populates = []
        self.compares = []

    def push_scope(self):
        env = dict()
        env["__up__"] = self.env
        self.env = env

        inject = dict()

    def pop_scope(self):
        self.env = self.env["__up__"]

    def lookup(self, name):
        return self.lookup_recursive(name, self.env)

    def lookup_recursive(self, name, table):
        if name in table:
            return table[name]
        elif "__up__" in table:
            return self.lookup_recursive(name, table["__up__"])
        else:
            return False

    def create_connect(self, ele1, ele2, port1, port2):
        return Connect(desugar_name(ele1), desugar_name(ele2), port1, port2)

    def instantiate_arg(self, instance, param, i, arg):
        m = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z0-9]+)]', arg)
        if m:
            if not m.group(2) == param:
                raise "Parameterized element instance %s[%s] is instantiated with state instance %s." \
                      % (instance, param, arg)
            return m.group(1) + str(i)
        else:
            return arg

    def process(self, x):
        if isinstance(x, Program):
            statements = []
            for st in x.statements:
                ret = self.process(st)
                if isinstance(ret, tuple) or isinstance(ret, list):
                    for e in ret:
                        if e:
                            statements.append(e)
                elif ret:
                    statements.append(ret)
            return Program(*statements)

        elif isinstance(x, Composite):
            self.push_scope()
            p = self.process(x.program)
            self.pop_scope()
            return Composite(x.name, x.inports, x.outports, x.thread_ports, x.state_params, p)

        elif isinstance(x, Spec):
            if self.spec:
                return self.process(Program(*x.statements)).statements
            else:
                return None

        elif isinstance(x, Impl):
            if not self.spec:
                return self.process(Program(*x.statements)).statements
            else:
                return None

        elif isinstance(x, ElementInstance):
            m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', x.name)
            if m:
                name = m.group(1)
                n = int(m.group(2))
                self.env[name] = n
                ret = []
                for i in range(n):
                    args = [self.instantiate_arg(name, m.group(2), i, arg) for arg in x.args]
                    ret.append(ElementInstance(x.element, name + str(i), args))
                return ret
            else:
                return ElementInstance(x.element, desugar_name(x.name), [desugar_name(arg) for arg in x.args])

        elif isinstance(x, CompositeInstance):
            m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', x.name)
            if m:
                name = m.group(1)
                n = int(m.group(2))
                self.env[name] = n
                ret = []
                for i in range(n):
                    args = [self.instantiate_arg(name,m.group(2),i,arg) for arg in x.args]  # TODO: test
                    ret.append(CompositeInstance(x.element, name + str(i), args))
                return ret
            else:
                return x

        elif isinstance(x, StateInstance):
            m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', x.name)
            if m:
                name = m.group(1)
                n = int(m.group(2))
                self.env[name] = n
                return [StateInstance(x.state, name + str(i), concretize_init_as(x.init, str(i), str(n)))
                        for i in range(n)]
            else:
                return StateInstance(x.state, x.name, concretize_init(x.init))

        elif isinstance(x, Connect):
            m1 = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.ele1)
            m2 = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.ele2)
            if m1:
                n1 = self.lookup(m1.group(1))
            else:
                n1 = None
            if m2:
                n2 = self.lookup(m2.group(1))
            else:
                n2 = None

            if n1 and n2:
                if m1.group(2) == m2.group(2):
                    if not n1 == n2:
                        raise Exception("The number of '%s' is not equal to the number of '%s'."
                                        % (x.ele1, x.ele2))
                    return [self.create_connect(m1.group(1) + str(i), m2.group(1) + str(i), x.out1, x.in2)
                            for i in range(n1)]
                else:
                    ret = []
                    for i1 in n1:
                        for i2 in n2:
                            ret.append(self.create_connect(m1.group(1) + str(i1), m2.group(1) + str(i2), x.out1, x.in2))
                    return ret
            elif n1:
                return [self.create_connect(m1.group(1) + str(i), x.ele2, x.out1, x.in2) for i in range(n1)]
            elif n2:
                return [self.create_connect(x.ele1, m2.group(1) + str(i), x.out1, x.in2) for i in range(n2)]
            else:
                return self.create_connect(x.ele1, x.ele2, x.out1, x.in2)

        elif isinstance(x, InternalTrigger):
            m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', x.name)
            if m:
                n = int(m.group(2))
                return [InternalTrigger(m.group(1) + str(i)) for i in range(n)]
            else:
                return InternalTrigger(desugar_name(x.name))

        elif isinstance(x, ResourceMap):
            m_rs = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.resource)
            m_inst = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.instance)
            if m_rs and m_inst:
                assert m_rs.group(2) == m_inst.group(2), \
                    ("Parameterized instance '%s' is mapped to parameterized resource '%s'. Parameters are unmatched."
                     % (x.instance, x.resource))

                n = self.lookup(m_inst.group(1))
                return [ResourceMap(m_rs.group(1) + str(i), m_inst.group(1) + str(i)) for i in range(n)]
            elif m_inst:
                n = self.lookup(m_inst.group(1))
                return [ResourceMap(desugar_name(x.resource), m_inst.group(1) + str(i)) for i in range(n)]
            elif m_rs:
                raise Exception("Non-parameterized instance '%s' cannot be mapped to parameterized resource '%s'"
                                % (x.instance, x.resource))
            else:
                return ResourceMap(desugar_name(x.resource), desugar_name(x.instance))

        elif isinstance(x, ResourceOrder):
            m_a = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.a)
            m_b = re.match('([a-zA-Z0-9_]+)\[([a-zA-Z]+)]', x.b)
            if m_a and m_b:
                if m_a.group(2) == m_b.group(2):
                    n = self.lookup(m_a.group(1))
                    return [ResourceOrder(m_a.group(1) + str(i), m_b.group(1) + str(i)) for i in range(n)]
                else:
                    n_a = self.lookup(m_a.group(1))
                    n_b = self.lookup(m_b.group(1))
                    ret = []
                    for i in range(n_a):
                        for j in range(n_b):
                            ret.append(ResourceOrder(m_a.group(1) + str(i), m_b.group(1) + str(j)))
                    return ret
            elif m_a:
                n = self.lookup(m_a.group(1))
                return [ResourceOrder(m_a.group(1) + str(i), desugar_name(x.b)) for i in range(n)]
            elif m_b:
                n = self.lookup(m_b.group(1))
                return [ResourceOrder(desugar_name(x.a), m_b.group(1) + str(i)) for i in range(n)]
            else:
                return ResourceOrder(desugar_name(x.a), desugar_name(x.b))

        elif isinstance(x, APIFunction):
            m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', x.name)
            if m:
                n = int(m.group(2))
                return [APIFunction(m.group(1) + str(i), x.call_types, x.return_type, x.default_val) for i in range(n)]
            else:
                return APIFunction(desugar_name(x.name), x.call_types, x.return_type, x.default_val)

        elif isinstance(x, PopulateState):
            self.populates.append(x.clone())

        elif isinstance(x, CompareState):
            self.compares.append(x.clone())

        else:
            return x


def desugar_name(name):
    m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', name)
    if m:
        return m.group(1) + m.group(2)
    else:
        return name
