from dsl import *
from elements_library import *

classify = create_element_instance("choose", [Port("in", ["int"])], [Port("out1", ["int"]), Port("out2", ["int"])],
                                   r'''
    (int x) = in();
    output switch {
        case x < 0: out1(x);
        else: out2(x);
    }
                                   ''')
Forward = create_identity("Forward", "int")
f1 = Forward()
f2 = Forward()
f3 = Forward()

x1, x2 = classify(None)
y1 = f1(x1)
y2 = f2(x2)
f3(y1)
f3(y2)

t = API_thread("run", ["int"], "int")
t.run(classify, f1, f2, f3)

c = Compiler()
c.testing = "out(run(3));"
c.generate_code_and_run([3])