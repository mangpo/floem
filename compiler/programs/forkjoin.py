from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
Chioce = create_element("Choice", [Port("in", ["int"])], [Port("out1", ["int"]), Port("out2", ["int"])],
                        r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')
Add = create_add("Add", "int")
Fork = create_fork("Fork", 2, "int")

fork = Fork()
chioce = Chioce()
add = Add()

@API("func")
def func(x):
    x1, x2 = fork(x)
    y1, y2 = chioce(x1)
    add(y1, x2)
    # TODO: allow add(y2, x2)
    add(y2)      # Already connect x2 to add, so must not connect it again
    out = add()  # Get 'out' port from add element once
    return out

c = Compiler()
c.testing = r'''
printf("%d\n",func(1));
printf("%d\n",func(2));
'''
c.desugar_mode = "compare"
c.generate_code_and_run([2, 4])
