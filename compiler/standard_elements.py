from graph import *
from program import *


def Fork(name, n, type):
    outports = [Port("out%d" % (i+1), [type]) for i in range(n)]
    calls = ["out%d(x);" % (i+1) for i in range(n)]
    src = "(%s x) = in(); output { %s }" % (type, " ".join(calls))
    return Element(name, [Port("in", [type])], outports, src)


def Fork_multi_values(name, n, types):
    args = []
    types_args = []
    for i in range(len(types)):
        arg = "_arg%d" % i
        args.append(arg)
        types_args.append("%s %s" % (types[i], arg))

    args_str = ",".join(args)
    outports = [Port("out%d" % (i + 1), types) for i in range(n)]
    calls = ["out%d(%s);" % ((i + 1), args_str) for i in range(n)]
    if len(types) == 0:
        src = "output { %s }" % (" ".join(calls))
    else:
        src = "(%s) = in(); output { %s }" % (",".join(types_args), " ".join(calls))
    return Element(name, [Port("in", types)], outports, src)


def IdentityElement(name, type):
    src = "(%s x) = in(); output { out(x); }" % type
    return Element(name, [Port("in", [type])], [Port("out", [type])], src)

Fork2 = Fork("Fork2", 2, "int")
Fork3 = Fork("Fork3", 3, "int")
Forward = IdentityElement("Forward", "int")
Add = Element("Add",
              [Port("in1", ["int"]), Port("in2", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in1() + in2(); output { out(x); }''')

Inc = Element("Inc",
              [Port("in", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in() + 1; output { out(x); }''')

Drop = Element("Drop",
              [Port("in", ["int"])],
              [],
              r'''in();''')

