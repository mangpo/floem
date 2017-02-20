from dsl import *


def create_fork(name, n, type):
    outports = [Port("out%d" % (i+1), [type]) for i in range(n)]
    calls = ["out%d(x);" % (i+1) for i in range(n)]
    src = "(%s x) = in(); output { %s }" % (type, " ".join(calls))
    return create_element(name, [Port("in", [type])], outports, src)


def create_identity(name, type):
    src = "(%s x) = in(); output { out(x); }" % type
    return create_element(name, [Port("in", [type])], [Port("out", [type])], src)


def create_add(name, type):
    src = "%s x = in1() + in2(); output { out(x); }" % type
    return create_element(name,
                          [Port("in1", [type]), Port("in2", [type])],
                          [Port("out", [type])],
                          r'''int x = in1() + in2(); output { out(x); }''')


def create_add1(name, type):
    src = "%s x = in() + 1; output { out(x); }" % type
    return create_element(name,
                          [Port("in", [type])],
                          [Port("out", [type])],
                          src)


def create_drop(name, type):
    return create_element(name,
                          [Port("in", [type])],
                          [],
                          r'''in();''')