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
        self.output2ele = {}   # map output port name to element name
        self.state_args = state_args

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
