from dsl import *
from elements_library import *

fork = create_fork_instance("myfork", 2, "int")
Inc = create_add1("inc", "int")
Add = create_add("add", "int")
inc = Inc()
add = Add()
display = create_element_instance("display", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

x1, x2 = fork(None)
y1 = inc(x1)
z = add(y1, x2)
display(z)

prod = API_thread("run", ["int"], None)
t = internal_thread("t")

prod.run(fork)
t.run(inc, add, display)

c = Compiler()
c.testing = r'''
run(1);
'''
c.generate_code_and_run([3])