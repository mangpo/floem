from dsl import *

Count = create_state("Count", "int count;", [0])
Forward = create_element("Identity",
            [Port("in", ["int"])],
            [Port("out", ["int"])],
            r'''local->count++; global->count++; int x = in(); printf("%d %d\n", local->count, global->count); output { out(x); }''',
            None,
            [("Count", "local"), ("Count", "global")]
            )
Print = create_element("Print",
            [Port("in", ["int"])],
            [],
            r'''printf("%d\n", in());''')

c_global = Count()
def unit(x0):
    c_local = Count()
    f1 = Forward("f1", [c_local, c_global])
    f2 = Forward("f2", [c_local, c_global])
    x1 = f1(x0)
    x2 = f2(x1)
    return x2

Unit = create_composite("Unit", unit)

x1 = Unit("u1")(None)
x2 = Unit("u2")(x1)
Print()(x2)

c = Compiler()
c.resource = False
c.remove_unused = False
c.testing = "u1_f1(123); u1_f1(42);"
c.generate_code_and_run([1,1,2,2,1,3,2,4,123, 3,5,4,6,3,7,4,8,42])