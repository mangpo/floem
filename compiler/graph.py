from graph_ir import *

class Graph:
    def __init__(self, default_process, original):

        self.instances = {}
        if original:
            self.elements = copy.copy(original.elements)
            self.states = copy.copy(original.states)
            self.state_instances = copy.copy(original.state_instances)
            # Inject and probe
            self.inject_populates = copy.copy(original.inject_populates)
            self.probe_compares = copy.copy(original.probe_compares)
        else:
            self.elements = {}
            self.states = {}
            self.state_instances = {}
            # Inject and probe
            self.inject_populates = {}
            self.probe_compares = {}

        self.state_order = []
        self.state_instance_order = []
        self.memory_regions = []

        self.threads_internal = []
        self.threads_API = []
        self.threads_order = []
        self.threads_roots = set()

        # Process
        self.processes = set()
        self.devices = set()
        self.thread2process = {}
        self.thread2device = {}
        self.process2device = {}
        self.default_process = default_process
        self.master_process = None

        # Per-packet state
        self.pipeline_states = {}

    def merge(self, other):
        assert other.default_process is 'tmp' or self.default_process == other.default_process, \
            "Graph merge failed -- mismatch default_process: %s vs %s." % (self.default_process, other.default_process)
        assert other.master_process is None or self.master_process == None or \
               self.master_process == other.master_process, \
            "Graph merge failed -- mismatch master_process: %s vs %s." % (self.master_process, other.master_process)
        self.merge_dict(self.elements, other.elements)
        self.merge_dict(self.instances, other.instances)
        self.merge_dict(self.states, other.states)
        self.merge_dict(self.state_instances, other.state_instances)
        self.merge_list(self.state_order, other.state_order)
        self.merge_list(self.state_instance_order, other.state_instance_order)
        self.merge_list(self.memory_regions, other.memory_regions)

        self.merge_list(self.threads_internal, other.threads_internal)
        self.merge_list(self.threads_API, other.threads_API)
        self.merge_list(self.threads_order, other.threads_order)
        self.threads_roots = self.merge_set(self.threads_roots, other.threads_roots)

        self.merge_dict(self.inject_populates, other.inject_populates)
        self.merge_dict(self.probe_compares, other.probe_compares)

        self.processes = self.merge_set(self.processes, other.processes)
        self.devices = self.merge_set(self.devices, other.devices)
        self.merge_dict(self.thread2process, other.thread2process)
        self.merge_dict(self.thread2device, other.thread2device)
        self.merge_dict(self.process2device, other.process2device)
        self.master_process = self.master_process or other.master_process

    @staticmethod
    def merge_dict(this, other):
        for key in other:
            if key not in this:
                this[key] = other[key]

    @staticmethod
    def merge_list(this, other):
        this += other

    @staticmethod
    def merge_set(this, other):
        return this.union(other)

    def __str__(self):
        s = "Graph:\n"
        # s += "  states: %s\n" % str(self.states)
        s += "  states: %s\n" % [str(self.state_instances[x].state) + "::" + x for x in self.state_instances.keys()]
        # s += "  elements: %s\n" % str(self.elements)
        # s += "  elements: %s\n" % [str(x) for x in self.instances.values()]
        s += "  elements:\n"
        for x in self.instances.values():
            s += "    " + str(x) + "\n"
        return s

    def print_graphviz(self):
        for name in self.instances:
            instance = self.instances[name]
            if instance.element.output_fire == "all":
                from_suffix = ""
            elif instance.element.output_fire == "one":
                from_suffix = "_f1"
            else:
                from_suffix = "_f0"

            for port in instance.output2ele:
                next_name, next_port = instance.output2ele[port]
                next = self.instances[next_name]
                if next.element.output_fire == "all":
                    to_suffix = ""
                elif next.element.output_fire == "one":
                    to_suffix = "_f1"
                else:
                    to_suffix = "_f0"

                print '%s%s -> %s%s [ label = "%s" ];' % (name, from_suffix, next_name, to_suffix, port)

    def is_state(self, state_name):
        return state_name in self.states

    def clear_APIs(self):
        self.threads_API = []
        self.threads_internal = []
        for instance in self.instances.values():
            instance.thread = None

    def has_element_instance(self, instance_name):
        return instance_name in self.instances

    def get_inport_argtypes(self, instance_name, port_name):
        try:
            inports = self.instances[instance_name].element.inports
            return [x for x in inports if x.name == port_name][0].argtypes
        except IndexError:
            raise UndefinedPort()
        except KeyError:
            raise UndefinedInstance()

    def get_outport_argtypes(self, instance_name, port_name):
        try:
            outports = self.instances[instance_name].element.outports
            return [x for x in outports if x.name == port_name][0].argtypes
        except IndexError:
            raise UndefinedPort()
        except KeyError:
            raise UndefinedInstance()

    def addState(self,state):
        if state.name in self.states:
            if not self.states[state.name] == state:
                raise RedefineError("State '%s' is already defined." % state.name)
            return False
        else:
            self.states[state.name] = state
            self.state_order.append(state.name)
            return True

    def addElement(self,element):
        if element.name in self.elements:
            if not self.elements[element.name] == element:
                raise RedefineError("Element '%s' is already defined." % element.name)
            return False
        else:
            self.elements[element.name] = element
            return True

    def addMemoryRegion(self, region):
        self.memory_regions.append(region)

    def newStateInstance(self, state, name, init=False):
        if state in self.states:
            s = self.states[state]
        else:
            s = State(state, None, None)
        ret = StateNode(name, s, init)
        self.state_instances[name] = ret
        self.state_instance_order.append(name)

    def newElementInstance(self, element, name, state_args=[], user_instance=None):
        if not element in self.elements:
            raise Exception("Element '%s' is undefined." % element)
        e = self.elements[element]
        ret = ElementNode(name, e, state_args, None)
        self.instances[name] = ret

        # Smart queue
        if isinstance(e.special, Queue):
            if e.special.enq == user_instance:
                e.special.enq = ret
            elif e.special.deq == user_instance:
                e.special.deq = ret
            elif e.special.scan == user_instance:
                e.special.scan = ret
            else:
                raise Exception("Element instance '%s' is link to smart queue '%s', but the queue doesn't link to the instance."
                                % (user_instance.name, e.special.name))

        # Check state types
        if not (len(state_args) == len(e.state_params)):
            raise Exception("Element '%s' requires %d state arguments. %d states are given."
                            % (e.name, len(e.state_params), len(state_args)))
        for i in range(len(state_args)):
            (type, local_name) = e.state_params[i]
            s = state_args[i]
            state = self.state_instances[s].state
            if not (state.name == type):
                raise Exception("Element '%s' expects state '%s'. State '%s' is given." % (e.name, type, state.name))

        return ret

    def copy_node_and_element(self, inst_name, suffix):
        instance = self.instances[inst_name]
        new_instance = instance.deep_clone(suffix)
        new_element = new_instance.element
        self.instances[new_instance.name] = new_instance
        self.elements[new_element.name] = new_element

    def connect(self, name1, name2, out1=None, in2=None, overwrite=False):
        i1 = self.instances[name1]
        i2 = self.instances[name2]
        e1 = i1.element
        e2 = i2.element

        out_argtypes = []
        if out1:
            assert (out1 in [x.name for x in e1.outports]), \
                "Port '%s' is undefined for element '%s'. Available ports are %s." \
                % (out1, name1, [x.name for x in e1.outports])
            out_argtypes += [x for x in e1.outports if x.name == out1][0].argtypes
        else:
            assert len(e1.outports) == 1,\
                "Element instance '%s' has multiple output ports. Please specify which port to connect." % name1
            out1 = e1.outports[0].name
            out_argtypes += e1.outports[0].argtypes

        in_argtypes = []
        if in2:
            assert (in2 in [x.name for x in e2.inports]), \
                "Port '%s' is undefined for element '%s'. Available ports are %s." \
                % (in2, name2, [x.name for x in e2.inports])
            in_argtypes += [x for x in e2.inports if x.name == in2][0].argtypes
        else:
            # If not specified, concat all ports together.
            if len(e2.inports) == 1:
                in2 = e2.inports[0].name
            else:
                in2 = [port.name for port in e2.inports]
            in_argtypes += sum([port.argtypes for port in e2.inports], []) # Flatten a list of list

        # Check types
        # if not(in_argtypes == out_argtypes):
        #     if out1 and in2:
        #         raise Exception("Mismatched ports -- output port '%s' of element '%s' and input port '%s' of element '%s': %s vs %s"
        #                         % (out1, name1, in2, name2, out_argtypes, in_argtypes))
        #     else:
        #         raise Exception("Mismatched ports -- output port of element '%s' and input port of element '%s': %s vs %s"
        #                         % (name1, name2, out_argtypes, in_argtypes))

        i1.connect_output_port(out1, i2.name, in2, overwrite)
        if isinstance(in2, str):
            i2.connect_input_port(in2, i1.name, out1)
        else:
            for port_name in in2:
                i2.connect_input_port(port_name, i1.name, out1)

    def disconnect(self, name1, name2, out1, in2):
        i1 = self.instances[name1]
        i2 = self.instances[name2]

        del i1.output2ele[out1]
        i2.input2ele[in2].remove((name1, out1))
        print name1

    def delete_instance(self, name):
        instance = self.instances[name]
        del self.instances[name]
        for port in instance.input2ele:
            l = instance.input2ele[port]
            for next_name, next_port in l:
                other = self.instances[next_name]
                this_name, this_port = other.output2ele[next_port]
                if this_name == name:
                    del other.output2ele[next_port]

        for port in instance.output2ele:
            next_name, next_port = instance.output2ele[port]
            other = self.instances[next_name]
            l = other.input2ele[next_port]
            new_l = []
            for this_name, this_port in l:
                if not this_name == name:
                    new_l.append((this_name, this_port))
            if len(new_l) == 0:
                del other.input2ele[next_port]
            else:
                other.input2ele[next_port] = new_l


    def get_thread_of(self, name):
        return self.instances[name].thread

    def set_thread(self, name, t):
        self.instances[name].thread = t

    def add_pipeline_state(self, inst_name, state_name):
        assert inst_name not in self.pipeline_states, \
            "Element instance '%s' was assigned to pipeline state '%s', but it is again assigned to '%s'." \
            % (inst_name, self.pipeline_states[inst_name], state_name)
        self.pipeline_states[inst_name] = state_name

    def check_input_ports(self):
        for instance in self.instances.values():
            instance.check_input_ports()

    def find_roots(self):
        """
        :return: roots of the graph (elements that have no parent)
        """
        not_roots = set()
        for name in self.instances:
            instance = self.instances[name]
            for (next, port) in instance.output2ele.values():
                not_roots.add(next)

        roots = set(self.instances.keys()).difference(not_roots)
        return roots

    def find_subgraph(self, root, subgraph):
        instance = self.instances[root]
        if instance.name not in subgraph:
            subgraph.add(instance.name)
            for inst,port in instance.output2ele.values():
                self.find_subgraph(inst, subgraph)
        return subgraph

    def find_subgraph_same_thread(self, root, subgraph, thread):
        instance = self.instances[root]
        if instance.name not in subgraph and instance.thread == thread:
            subgraph.add(instance.name)
            for inst,port in instance.output2ele.values():
                self.find_subgraph_same_thread(inst, subgraph, thread)
        return subgraph

    def remove_unused_elements(self, resource):
        used = set([x.call_instance for x in self.threads_API])
        delete = []
        for name in self.instances:
            instance = self.instances[name]
            if instance.unused() and instance.name not in used:
                # No connection
                delete.append(name)

        for name in delete:
            del self.instances[name]

        if len(self.threads_roots) > 0:
            for name in delete:
                self.threads_roots.remove(name)

        if resource:
            for instance in self.instances.values():
                if instance.thread is None:
                    raise Exception("Element instance '%s' has not been assigned to any thread." % instance.name)


    def remove_unused_states(self):
        delete = []
        for name in self.state_instances:
            inst = self.state_instances[name]
            if len(inst.processes) == 0:
                delete.append(name)

        for name in delete:
            del self.state_instances[name]
            self.state_instance_order.remove(name)

    def is_start(self, my):
        for inst_list in my.input2ele.values():
            for name, port in inst_list:
                other = self.instances[name]
                if other.thread == my.thread:
                    return False
        return True

    def process_of_thread(self, t):
        if t in self.thread2process:
            return self.thread2process[t]
        else:
            return self.default_process

    def device_of_thread(self, t):
        if t in self.thread2device:
            return self.thread2device[t]
        else:
            return (target.CPU, [0])

'''
State initialization related functions
'''
class AddressOf:
    def __init__(self, of):
        self.of = of

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.of == other.of


def concretize_init(init):
    if isinstance(init, str):
        m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', init)
        if m:
            return [m.group(1) + str(i) for i in range(int(m.group(2)))]
        else:
            return init
    elif isinstance(init, list) or isinstance(init, tuple):
        return [concretize_init(x) for x in init]
    elif isinstance(init, AddressOf):
        m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', init.of)
        if m:
            return [AddressOf(m.group(1) + str(i)) for i in range(int(m.group(2)))]
        else:
            return init
    else:
        return init


def concretize_init_as(init, i, n):
    if isinstance(init, str):
        m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', init)
        if m:
            assert n == m.group(2), "The index of %s should be %s." % (init, n)
            return m.group(1) + i
        else:
            return init
    elif isinstance(init, list) or isinstance(init, tuple):
        return [concretize_init_as(x, i, n) for x in init]
    elif isinstance(init, AddressOf):
        m = re.match('([a-zA-Z0-9_]+)\[([0-9]+)]', init.of)
        if m:
            assert n == m.group(2), "The index of %s should be %s." % (init.of, n)
            return AddressOf(m.group(1) + i)
        else:
            return init
    else:
        return init


def get_str_init(init):
    if isinstance(init, str):
        return init
    elif isinstance(init, list) or isinstance(init, tuple):
        ret = ','.join([get_str_init(x) for x in init])
        return '{' + ret + '}'
    elif isinstance(init, AddressOf):
        return '&' + init.of
    else:
        return str(init)

