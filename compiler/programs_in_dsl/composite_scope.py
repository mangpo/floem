from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")

f1 = None
def compo(x):
    global f1
    f1 = Forward()
    return f1(x)

c = create_composite_instance("compo", compo)
t = API_thread("run", ["int"], "int")
t.run_start(f1)

c = Compiler()
c.testing = "out(run(123));"
c.generate_code_and_run([123])
