from ast import Element, Port
import re

def element_to_function(src, funcname, inports, output2func):
    port2args = {}
    for f in inports:
        match = False
        index = 0
        while not(match):
            p = src.find(f,index)
            #m = re.search(';([^=]+)=[ ]*' + funcname + '[ ]*\(([^\)]*)\)[ ]*;',src)
            if p == -1:
                raise Exception("Element '%s' never get data from input port '%s'." % (funcname,f))
            if p == 0 or re.search('[^a-zA-Z0-9_]',src[p-1]):
                last = max(0,src[:p].rfind(";"))
                next = src.find(";",p)
                stmt = src[last+1:next+1]
                src = src[:last+1] + src[next+1:]
                
                eq = stmt.find("=")
                if eq >= 0:
                    args_begin = stmt.find("(",eq)
                    args_end = stmt.find(")",eq)
                    args = stmt[args_begin+1:args_end].lstrip().rstrip()
                    if not(args == ""):
                        raise Exception("Cannot pass an argument when retrieving data from an input port.")
                    decl = stmt[:eq].lstrip().rstrip().lstrip("(").rstrip(")").lstrip().rstrip()
                    port2args[f] = decl.split(",")
                else:
                    port2args[f] = []
                match = True
            else:
                index = p + 1
                
        p = src.find(f,index)
        if p >= 0:
            raise Exception("Cannot get data from input port '%s' more than one time in element '%s'." % (f, funcname))

    for o in output2func:
        p = src.find(o + "(")
        if p == 0 or src[p-1] == " " or src[p-1] == "{" or src[p-1] == ";":
            src = src[:p] + output2func[o] + src[p+len(o):]

    args = []
    for port in inports:
        args = args + port2args[port]

    src = "void " + funcname + "(" + ", ".join(args) + ") {" + src + "}"
    print src
    return src
                                                              

def test1():
    src = r'''
  int i = in1();
  i = i + i;
  out(i+1);
'''
    element_to_function(src, "f", ["in1"], {"out": "g"})

def test2():
    e1 = Element("Power",
                [Port("in", ["int"])],
                [Port("out", ["int"])], 
                r'''
                int x = in();
                out(x*x);
                ''')
    e2 = Element("Add1",
                [Port("in", ["int"])],
                [Port("out", ["int"])], 
                r'''
                out(in()+1);
                ''')
    element_to_function(e1.code, e1.name, [x.name for x in e1.inports],
                        dict([(x.name, x.name + '_func') for x in e1.outports]))
    element_to_function(e2.code, e2.name, [x.name for x in e2.inports],
                        dict([(x.name, x.name + '_func') for x in e2.outports])) #: TODO: currently broken

test2()
