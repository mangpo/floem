from compiler import element_to_function
from graph import Element, Port
import unittest


def test_element(e):
    element_to_function(e.code, e.name, e.inports,
                        dict([(x.name, (x.name + '_func',None)) for x in e.outports]))

class TestElementToFunction(unittest.TestCase):

    def test_input_stmt(self):
        e1 = Element("Power",
                     [Port("in", ["int"])],
                     [Port("out", ["int"])], 
                     r'''int x = in(); out(x*x);''')
        test_element(e1)

    def test_input_expr(self):
        e2 = Element("Add1",
                     [Port("in", ["int"])],
                     [Port("out", ["int"])], 
                     r'''out(in()+1);''')
        test_element(e2)

    def test_multi_ports(self):
        e3 = Element("AddSub",
                     [Port("in1", ["int"]), Port("in2", ["int"])],
                     [Port("add_out", ["int"]), Port("sub_out", ["int"])], 
                     r'''
                     int a = in1(); int b = in2();
                     add_out(a+b); sub_out(a-b);
                     ''')
        test_element(e3)

    def test_no_arg(self):
        e4 = Element("Print",
                     [Port("in", [])],
                     [Port("out", [])], 
                     r'''in(); printf("hello\n"); out();''')
        test_element(e4)

    def expect_exception(self,e,s):
        try:
            test_element(e)
        except Exception as e:
            self.assertTrue(s in str(e))
        else:
            self.fail('Exception is not raised.')
        

    def test_arg_to_inport(self):
        e = Element("Print",
                    [Port("in", [])],
                    [], 
                    r'''in(123);''')
        self.expect_exception(e,"Cannot pass an argument when retrieving data from an input port.")

    def test_argtype_mismatch(self):
        e = Element("Print",
                    [Port("in", ["int"])],
                    [], 
                    r'''float x = in();''')
        self.expect_exception(e,"Argument types mismatch")

    def test_no_value_in_expr(self):
        e = Element("Print",
                    [Port("in", [])],
                    [Port("out",["int"])], 
                    r'''out(in());''')
        self.expect_exception(e,"It cannot be used as an expression.")

    def test_two_values_in_expr(self):
        e = Element("Print",
                    [Port("in", ["int", "int"])],
                    [Port("out",["int"])], 
                    r'''out(in());''')
        self.expect_exception(e,"It cannot be used as an expression.")
        

if __name__ == '__main__':
    unittest.main()
