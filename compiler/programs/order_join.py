from dsl import *

Fork = create_element("Fork", [Port("in", ["int", "int"])],
                      [Port("to_add", ["int", "int"]), Port("to_sub", ["int", "int"])],
                      r'''(int x, int y) = in(); output { to_add(x,y); to_sub(x,y); }''')

Add = create_element("Add", [Port("in", ["int", "int"])], [Port("out", ["int"])],
                     r'''(int x, int y) = in(); output { out(x+y); }''')

Sub = create_element("Sub", [Port("in", ["int", "int"])], [Port("out", ["int"])],
                     r'''(int x, int y) = in(); output { out(x-y); }''')

Print = create_element("Print", [Port("in1", ["int"]), Port("in2", ["int"])], [],
                       r'''printf("%d %d\n",in1(), in2());''')

fork = Fork()
add = Add()
sub = Sub()
p = Print()

in1, in2 = fork(None)
out1 = add(in1)
out2 = sub(in2)
p(out1, out2)

t = API_thread("myfork", ["int", "int"], None)
t.run(fork, add, sub, p)
t.run_order(sub, add)

c = Compiler()
c.testing = "myfork(10, 7);"
c.generate_code_and_run([17,3])