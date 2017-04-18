from dsl import *
from elements_library import *

Gen = create_element("Gen", [], [Port("out", ["int"])], "output { out(0); }")
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

def compo():
    gen = Gen()
    p = Print()
    p(gen())

    t = internal_thread("t")
    t.run(gen, p)

Compo = create_composite("Compo", compo)
c1 = Compo()
c2 = Compo()

c = Compiler()
c.generate_code_and_run()

