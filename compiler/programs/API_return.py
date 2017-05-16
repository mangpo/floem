from dsl import *
from elements_library import *

Inc = create_add1("Inc", "int")
Fork = create_fork("Fork", 2, "int")
Display = create_element("Display", [Port("in", ["int"])], [], r'''printf("disp %d\n", in());''')

inc = Inc()
fork = Fork()
display = Display()

x = inc(None)
x1, x2 = fork(x)
display(x2)

t = API_thread("run", ["int"], "int")
t.run(inc, fork, display)

c = Compiler()
c.testing = "out(run(3));"
c.generate_code_and_run(['disp', 4, 4])