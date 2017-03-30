from elements_library import *


Inject = create_inject("Inject", "int", 10, "gen_func")
Probe = create_probe("Probe", "int", 10, "cmp_func")
Forward = create_identity("Forward", "int")

def compo_func():
    f2 = Forward()
    f3 = Forward()
    inject = Inject()
    probe = Probe()

    return f3(probe(f2(inject())))


compo = create_composite_instance("compo", compo_func)

c = Compiler()
c.include = r'''
int gen_func(int i) { return i; }
'''
c.testing = "usleep(1000000);"
c.generate_code_and_run(range(10))