from dsl import *

gen = create_element_instance("gen", [], [Port("out", ["int"])],
                              r'''
    for(int i=0; i<10; i++)
        out(i);
    output multiple;
                              ''')

display = create_element_instance("display", [Port("in", ["int"])], [],
                                  r'''
    printf("%d\n", in());
                                  ''')

@API("batch_run")
def batch_run():
    display(gen())

c = Compiler()
c.testing = r'''
batch_run();
'''

c.generate_code_and_run(range(10))