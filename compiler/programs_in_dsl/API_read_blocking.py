from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")
f1 = Forward()
f2 = Forward()

x = f2(f1(None))

t1 = API_thread("put", ["int"], None)
t2 = API_thread("get", [], "int")
t1.run(True, f1)
t2.run(True, f2)

c = Compiler()
c.testing = "put(42); out(get()); put(123); out(get());"
c.generate_code_and_run([42,123])