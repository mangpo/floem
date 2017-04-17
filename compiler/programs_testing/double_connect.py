from dsl import *

gen = create_element_instance("gen",
              [],
              [Port("out1", ["int"]), Port("out2", ["int"])],
               r'''
output { out1(1); out2(2); }
''')

display = create_element_instance("print",
              [Port("in1", ["int"]), Port("in2", ["int"])],
              [],
               r'''
int x = in1();
int y = in2();
printf("%d %d\n", x, y);
''')

x, y = gen()
display(x,y)

c = Compiler()
c.remove_unused = False
c.testing = "gen();"
c.generate_code_and_run([1,2])
