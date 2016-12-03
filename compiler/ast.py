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
        self.output2func = {}

    def connectPort(self,port,f):
        self.output2func[port] = f

class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes
        
