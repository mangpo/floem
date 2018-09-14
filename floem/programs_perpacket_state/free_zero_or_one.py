from floem import *

choose = create_element_instance("choose", [Port("in", ["int"])], [Port("out0", []), Port("out1", [])],
                                   r'''
    (int x) = in();
    state.a = x;
    output switch {
        case (x % 3 == 0): out0();
        case (x % 3 == 1): out1();
    }
                                   ''')

Display = create_element("display", [Port("in", [])], [],
                                  r'''
    printf("%d\n", state.a);
                                  ''')
display1 = Display()
display2 = Display()
display3 = Display()

fork = create_element_instance("myfork", [Port("in", [])], [Port("out0", []), Port("out1", [])],
                               r'''
    output { out0(); out1(); }
                               ''')

state = create_state("mystate", "int a;")
pipeline_state(choose, "mystate")

x1, x2 = choose(None)
display1(x1)
x2, x3 = fork(x2)
display2(x2)
display3(x3)

f = API_thread("run", ["int"], None)
f.run(choose, display1)

t2 = internal_thread("t2")
t2.run(fork, display2)

t3 = internal_thread("t3")
t3.run(display3)

c = Compiler()
c.testing = r'''
run(0); run(1);
usleep(1000);
run(2);
'''
c.generate_code_and_run([0,'free!', 1, 1, 'free!', 'free!'])