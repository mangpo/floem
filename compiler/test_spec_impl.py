from dsl import *
from elements_library import *
import unittest


def get_element(name=None):
    return create_add1("Inc", "int")


def get_element_instance(name=None):
    Inc = create_add1("Inc", "int")
    return Inc(name)


def get_composite():
    Inc = create_add1("Inc", "int")

    def composite(x):
        f1 = Inc()
        f2 = Inc()
        return f2(f1(x))
    return create_composite("Compo", composite)


def get_composite_instance():
    Inc = create_add1("Inc", "int")
    def composite(x):
        f1 = Inc()
        f2 = Inc()
        return f2(f1(x))
    return create_composite_instance("compo", composite)


def get_spec_impl_instance():
    Inc = create_add1("Inc", "int")
    def spec(x):
        f1 = Inc()
        return f1(x)
    def impl(x):
        f1 = Inc()
        f2 = Inc()
        return f2(f1(x))
    return create_spec_impl("spec_impl", spec, impl)


def get_nested_compo_compo():
    Inc = create_add1("Inc", "int")
    def compo_outer(x):
        def compo_inner(x):
            f1 = Inc()
            f2 = Inc()
            return f2(f1(x))
        Compo = create_composite("compo_inner", compo_inner)
        compo1 = Compo()
        compo2 = Compo()
        return compo2(compo1(x))

    return create_composite_instance("compo_outer", compo_outer)


def get_nested_compo_spec():
    Inc = create_add1("Inc", "int")

    def compo_outer(x):
        def spec(x):
            f1 = Inc()
            return f1(x)

        def impl(x):
            f1 = Inc()
            f2 = Inc()
            return f2(f1(x))

        specimpl = create_spec_impl("compare", spec, impl)
        return specimpl(x)

    return create_composite_instance("compo_outer", compo_outer)


def get_nested_spec_compo():
    Inc = create_add1("Inc", "int")

    def spec(x):
        f1 = Inc()
        return f1(x)

    def impl(x):
        def compo_inner(x):
            f1 = Inc()
            f2 = Inc()
            return f2(f1(x))

        compo = create_composite_instance("compo_inner", compo_inner)
        return compo(x)

    return create_spec_impl("compare_outer", spec, impl)


class TestSpecImpl(unittest.TestCase):

    def test_connect_ele_compo(self):
        reset()
        e1 = get_element_instance("f")
        compo = get_composite_instance()
        e2 = get_element_instance()

        e2(compo(e1(None)))

        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.testing = 'f(0);'
        c.generate_code_and_run([4])

    def test_connect_ele_specimpl(self):
        reset()
        e1 = get_element_instance("f")
        compo = get_spec_impl_instance()
        e2 = get_element_instance()

        x1 = e1(None)
        x2 = compo(x1)
        x3 = e2(x2)

        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.desugar_mode = "compare"
        c.testing = '_spec_f(0); _impl_f(0);'
        c.generate_code_and_run([3,4])

    def test_specimpl_compo(self):
        reset()
        Compo = get_composite()
        e1 = get_element_instance("f")  # 1
        s2 = get_spec_impl_instance()  # 1/2
        c3 = Compo()  # 2
        c3(s2(e1(None)))

        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.desugar_mode = "impl"
        c.testing = 'f(0);'
        c.generate_code_and_run([5])


    def test_connect_compo_specimpl(self):
        reset()
        Compo = get_composite()
        e1 = get_element_instance("f")  # 1
        c1 = Compo()  # 2
        c2 = Compo()  # 2
        s1 = get_spec_impl_instance() # 1/2
        s2 = get_spec_impl_instance() # 1/2
        c3 = Compo()  # 2

        c3(s2(s1(c2(c1(e1(None))))))
        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.desugar_mode = "compare"
        c.testing = '_spec_f(0); _impl_f(0);'
        c.generate_code_and_run([9, 11])

    def test_nested(self):
        reset()
        e1 = get_element_instance("f")  # 1
        c1 = get_nested_compo_compo()   # 4
        c2 = get_nested_compo_spec()    # 1/2
        c3 = get_nested_spec_compo()    # 1/2
        e2 = get_element_instance()     # 1

        e2(c3(c2(c1(e1(None)))))
        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.desugar_mode = "compare"
        c.testing = '_spec_f(0); _impl_f(0);'
        c.generate_code_and_run([8,10])

    def test_nested2(self):
        reset()
        e1 = get_element_instance("f")
        c1 = get_nested_compo_spec()
        c2 = get_nested_compo_spec()

        c2(c1(e1(None)))
        c = Compiler()
        c.resource = False
        c.remove_unused = False
        c.desugar_mode = "compare"
        c.testing = '_spec_f(0); _impl_f(0);'
        c.generate_code_and_run([3, 5])
