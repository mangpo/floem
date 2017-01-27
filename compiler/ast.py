class Element:

    def __init__(self, name, inports, outports, code, local_state=None, state_params=[]):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = code
        self.local_state = local_state
        self.state_params = state_params


class ElementInstance:
    def __init__(self, name, element, state_args):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to (element name, port)
        self.output2connection = {}
        self.state_args = state_args
        self.thread = None

    def connectPort(self, port, f, fport):
        self.output2ele[port] = (f, fport)


class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes


class State:
    def __init__(self, name, content, init=None):
        self.name = name
        self.content = content
        self.init = init


class Graph:
    def __init__(self, elements, states=[]):
        self.elements = {}
        self.instances = {}
        self.states = {}
        self.state_instances = {}
        for e in elements:
            self.elements[e.name] = e
        for s in states:
            self.states[s.name] = s

        self.threads_entry_point = set()
        self.threads_api = set()
        self.threads_internal = set()

    def newStateInstance(self, state, name):
        s = self.states[state]
        self.state_instances[name] = s

    def defineInstance(self, element, name, state_args=[]):
        e = self.elements[element]
        self.instances[name] = ElementInstance(name, e, state_args)

        # Check state types
        if not (len(state_args) == len(e.state_params)):
            raise Exception("Element '%s' requires %d state arguments. %d states are given."
                            % (e.name, len(e.state_params), len(state_args)))
        for i in range(len(state_args)):
            (type, local_name) = e.state_params[i]
            s = state_args[i]
            state = self.state_instances[s]
            if not (state.name == type):
                raise Exception("Element '%s' expects state '%s'. State '%s' is given." % (e.name, type, state.name))

    def connect(self, name1, name2, out1=None, in2=None):
        i1 = self.instances[name1]
        i2 = self.instances[name2]
        e1 = i1.element
        e2 = i2.element

        # TODO: check type
        if out1:
            assert (out1 in [x.name for x in e1.outports]), \
                "Port '%s' is undefined. Aviable ports are %s." \
                % (out1, [x.name for x in e1.outports])
        else:
            assert (len(e1.outports) == 1)
            out1 = e1.outports[0].name

        if in2:
            assert (in2 in [x.name for x in e2.inports]), \
                "Port '%s' is undefined. Aviable ports are %s." \
                % (in2, [x.name for x in e2.inports])
        else:
            assert (len(e2.inports) == 1)
            # Leave in2 = None if there is only one port.

        i1.connectPort(out1, i2.name, in2)

    def external_api(self, instance):
        self.threads_api.add(instance)
        self.threads_entry_point(instance)

    def internal_trigger(self, instance):
        self.threads_internal.add(instance)
        self.threads_entry_point(instance)

    def find_roots(self):
        """
        :return: roots of the graph (elements that have no parent)
        """
        not_roots = set()
        for name in self.instances:
            instance = self.instances[name]
            for (next,port) in instance.output2ele.values():
                not_roots.add(next)

        roots = set(self.instances.keys()).difference(not_roots)
        return roots

    def assign_threads(self):
        """
        1. Assign thread to each element. Each root and each element marked API or trigger has its own thread.
        For each remaining element, assign its thread to be the same as its first parent's thread.
        2. Mark "save" to an output port if it connects to a join element or an element with a different thread.
        3. Mark "connect" to an output port if it is the last port that connects a join element with the same threads.
        :return: void
        """
        roots = self.find_roots()
        entry_points = roots.union(self.threads_entry_point)
        last = {}
        for root in roots:
            self.assign_thread_dfs(self.instances[root], entry_points, root, last)

        for (instance,out) in last.values():
            instance.output2connect[out] = "connect"

    def assign_thread_dfs(self, instance, roots, name, last):
        """Traverse the graph in DFS fashion to assign threads.

        :param instance: current element instance
        :param roots: a set of thread entry elements
        :param name: current thread
        :param last: a map to decide where to marl "connect"
        :return:
        """
        if instance.thread is None:
            if instance.name in roots:
                name = instance.name
            instance.thread = name
            for out in instance.output2ele:
                (next,port) = instance.output2ele[out]
                self.assign_thread_dfs(next, roots, name, last)
                # Mark "save" because it connects to a join element.
                if len(next.element.inports) > 1:
                    instance.output2connect[out] = "save"
                    if next.thread == instance.thread:
                        last[next.name] = (instance,out)  # Potential port to mark "connect"
                # Mark "save" because it connects to an element with a different thread.
                if not(next.thread == instance.thread):
                    instance.output2connect[out] = "save"