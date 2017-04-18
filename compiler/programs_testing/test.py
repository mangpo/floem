from dsl import *

Inc = create_element("Inc", [Port("in", ["int"])], [Port("out", ["int"])],
  "int x = in() + 1; output { out(x); }")
inc1 = Inc()
inc2 = Inc()

inc2(inc1(None))

t = API_thread("add2", ["int"], "int")
t.run_start(inc1, inc2)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = r'''printf("%d\n", add2(10));'''
c.generate_code_and_run()