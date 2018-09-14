from floem import *

fork = create_element_instance("myfork", [Port("in", ["int"])], [Port("out0", []), Port("out1", [])],
                                 r'''
    int x = in();
    state.a = x;
    state.b = x;
    output { out0(); out1(); }
                                 ''')

inc = create_element_instance("inc", [Port("in", [])], [Port("out", [])],
                                 r'''
    state.a++;
    output { out(); }
                                 ''')  # TODO: def & use

add = create_element_instance("add", [Port("in0", []), Port("in1", [])], [Port("out", [])],
                                 r'''
    state.sum = state.a + state.b;
    output { out(); }
                                 ''')

display = create_element_instance("display", [Port("in", [])], [], r'''printf("%d\n", state.sum);''')

state = create_state("mystate", "int a; int b; int sum;")
pipeline_state(fork, "mystate")

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
c.generate_code_and_run([3, 'free!'])