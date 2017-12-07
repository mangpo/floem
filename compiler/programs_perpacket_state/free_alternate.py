from dsl import *

save = create_element_instance("save", [Port("in", ["int"])], [Port("out", [])],
                                   r'''
    (int x) = in();
    state.a = x;
    output { out(); }
                                   ''')

nop = create_element_instance("nop", [Port("in", [])], [Port("out", [])],
                                   r'''
    output { out(); }
                                   ''')

display = create_element_instance("display", [Port("in", [])], [],
                                  r'''
    printf("%d\n", state.a);
                                  ''')

display(nop(save(None)))

state = create_state("mystate", "int a;")
pipeline_state(save, "mystate")


f = API_thread("run", ["int"], None)
#f.run(save, display)
f.run_order(save, display)

t2 = internal_thread("t2")
t2.run(nop)

c = Compiler()
c.testing = r'''
run(0); run(3);
'''
c.generate_code_and_run([0,'free!', 3, 'free!'])