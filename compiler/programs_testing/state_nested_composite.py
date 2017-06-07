from dsl import *
from elements_library import *

Count = create_state("Count", "int count;", [0])
Forward = create_element("Identity", [Port("in", ["int"])], [Port("out", ["int"])],
                         r'''this->count++; int x = in(); output { out(this->count); }''', [("Count", "this")])
Print = create_element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());''')

count = Count()

def outer_unit(x):
    def inner_unit(x):
        return Forward("f", [count])(x)
    InnerUnit = create_composite("InnerUnit", inner_unit)
    inner_unit = InnerUnit("inner_unit")
    return inner_unit(x)

OuterUnit = create_composite("OuterUnit", outer_unit)
outer_unit = OuterUnit("outer_unit")

ID = create_identity("ID", "int")
x1 = ID("start")(None)
x2 = outer_unit(x1)
Print()(x2)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = "start(11); start(22); start(33);"
c.generate_code_and_run([1,2,3])
