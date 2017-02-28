from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")

t = API_thread("func", ["int"], "int")


@composite_instance_at("compo", t)
def compo(x):
    f1 = Forward()
    f2 = Forward()

    t.start(f1)
    return f2(f1(x))

y = compo(None)

c = Compiler()
c.testing = "out(func(42)); out(func(123));"
c.generate_code_and_run([42, 123])