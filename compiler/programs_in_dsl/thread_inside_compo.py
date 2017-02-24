from dsl import *
from elements_library import *

Gen = create_element("Gen", [], [Port("out", ["int"])], "output { out(0); }")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

def compo():
    gen = Gen()
    p = Print()
    p(gen())

    t = internal_thread("t")
    t.run_start(gen, p)

Compo = create_composite("Compo", compo)
c1 = Compo()
c2 = Compo()

c = Compiler()
c.triggers = True
c.testing = "run_threads(); usleep(1000); kill_threads();"
c.generate_code_and_run()

