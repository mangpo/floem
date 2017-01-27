class Element:

    def __init__(self, name, inports, outports, code):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = code


class ElementInstance:
    def __init__(self,name,element):
        self.name = name
        self.element = element
        self.output2ele = {}   # map output port name to element name

    def connectPort(self, port, f, fport):
        self.output2ele[port] = (f, fport)

class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes
