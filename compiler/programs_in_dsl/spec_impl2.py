
from elements_library import *

Forward = create_identity("Forward", "int")
f = Forward()
g = Forward()


# METHOD 2: more concise
def connector_spec(x):
    c = Forward()
    return c(x)

def connector_impl(x):
    c1 = Forward()
    c2 = Forward()
    return c2(c1(x))

connector = create_spec_impl_instance("connector", connector_spec, connector_impl)
g(connector(f(None)))

# METHOD 3: easy but problematic
def spec():
    c = Forward()
    y = g(c(f(None)))  # problem: how to connect y?

def impl():
    c1 = Forward()
    c2 = Forward()
    y = g(c2(c1(f(None))))  # problem: how to connect y?






