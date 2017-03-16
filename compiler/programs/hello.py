from dsl import *

Fork = create_element("Fork",
            [Port("in", ["int","int"])],
            [Port("to_add", ["int","int"]), Port("to_sub", ["int","int"])],
            r'''(int x, int y) = in(); output { to_add(x,y); to_sub(x,y); }'''
            )

Add = create_element("Add",
            [Port("in", ["int","int"])],
            [Port("out", ["int"])],
            r'''(int x, int y) = in(); output { out(x+y); }''')

Sub = create_element("Sub",
            [Port("in", ["int","int"])],
            [Port("out", ["int"])],
            r'''(int x, int y) = in(); output { out(x-y); }''')

Print = create_element("Print",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n",in());''')

fork = Fork()
add = Add()
sub = Sub()
p = Print()

in1, in2 = fork(None)
out1 = add(in1)
out2 = sub(in2)
p(out1)
p(out2)

t = API_thread("myfork", ["int", "int"], None)
t.run_start(fork, add, sub, p)

c = Compiler()
c.testing = "myfork(10, 7);"
c.generate_code_and_run([17,3])