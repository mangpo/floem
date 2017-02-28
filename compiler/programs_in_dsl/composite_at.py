from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")

def compo(x, t):
    f1 = Forward()
    f2 = Forward()

    t.start(f1)
    return f2(f1(x))

compo_inst = create_composite_instance("compo", compo)
t = API_thread("func", ["int"], "int")
t.run(compo_inst)

compo_inst(None, t)

c = Compiler()
c.testing = "out(func(42)); out(func(123));"
c.generate_code_and_run([42, 123])