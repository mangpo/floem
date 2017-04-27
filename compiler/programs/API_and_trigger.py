from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

@API_implicit_outputs("run")
def xxx(x):
    f = Forward()
    return f(x)

@internal_trigger("internal1")
def i1(x):
    f = Forward()
    return f(x)

@internal_trigger("internal2")
def i2(x):
    f = Forward()
    p = Print()
    p(f(x))

i2(i1(xxx(None)))

c = Compiler()
c.testing = "run(123); run(42); usleep(1000);"
c.generate_code_and_run([123,42])