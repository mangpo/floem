from dsl import *
from elements_library import *

Forward = create_identity("Forward", "int")

@API_implicit_outputs("put")
def put(x):
    f1 = Forward()
    return f1(x)

@API_implicit_inputs("get")
def get(x):
    f2 = Forward()
    return f2(x)

get(put(None))

c = Compiler()
c.testing = "put(42); out(get()); put(123); out(get());"
c.generate_code_and_run([42,123])