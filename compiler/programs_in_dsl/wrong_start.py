from dsl import *
from elements_library import *

Gen = create_element("Gen", [], [Port("out", ["int"])],
                     "output { out(1); }")
Forward = create_identity("Forward", "int")
Drop = create_drop("Drop", "int")

gen = Gen()
f = Forward()
drop = Drop()
drop(f(gen()))

gen2 = Gen()
f2 = Forward()
drop2 = Drop()
drop2(f2(gen2()))

t = internal_thread("t")
t.run_start(gen, f, drop, gen2, f2, drop2)
#t.run_order(drop, gen2)

#t2 = internal_thread("t2")
#t2.run_start(gen2, f2, drop2)

c = Compiler()
c.triggers = True
c.testing = "run_threads(); usleep(1000); kill_threads();"
c.generate_code_and_run()