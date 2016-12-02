class Element:

    def __init__(self, name, inports, outports, code):
        self.name = name
        self.inports = inports
        self.outports = outports
        self.code = code


class Port:
    def __init__(self, name, argtypes):
        self.name = name
        self.argtypes = argtypes
        
