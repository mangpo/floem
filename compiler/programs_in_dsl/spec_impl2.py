
from elements_library import *

Forward = create_identity("Forward", "int")
f = Forward()
g = Forward()


# METHOD 2: more concise
def connector_funcs(spec,x):
    if spec:
        c = Forward()
        return c(x)
    else:
        c1 = Forward()
        c2 = Forward()
        return c2(c1(x))

connector = create_spec_impl_instance("connector", connector_func)
g(connector(f(None)))

# METHOD 3: easy but problematic
def spec():
    c = Forward()
    y = g(c(f(None)))  # problem: how to connect y?

def impl():
    c1 = Forward()
    c2 = Forward()
    y = g(c2(c1(f(None))))  # problem: how to connect y?






