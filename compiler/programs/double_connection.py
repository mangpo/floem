from dsl import *
from elements_library import *

gen = create_element_instance("gen", [Port("in", ["int"])], [Port("out", ["int"])],
                              r'''int x = in(); output { out(x); }''')
display = create_element_instance("display", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')


@API("run")
def run(x):
    y = gen(x)
    display(y)
    display(y)

c = Compiler()
c.testing = "run(123); run(42);"
c.generate_code_and_run([123,123,42,42])  # TODO: Is this the semantics we want?
