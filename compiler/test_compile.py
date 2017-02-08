from compiler import *
from program import *
from standard_elements import *
import os
import unittest


class TestCompile(unittest.TestCase):

    def test_pass(self):
        tests = ["hello.py",
                 "join.py",
                 "join_multiple.py",
                 "join_nested.py",
                 "join_both_both.py",
                 "join_call_order.py",
                 "join_call_order2.py",
                 "buffer.py",
                 "parallel_pipeline.py",
                 "state_local.py",
                 "state_shared.py",
                 "state_nested_composite.py",
                 "composite.py",
                 "composite_thread_port.py",
                 "state_nested_composite.py",
                 "API_increment.py",
                 "API_read_blocking.py",
                 "API_read_non_blocking.py",
                 "API_read_non_blocking2.py"
                 ]

        for test in tests:
            exit = os.system("python programs/" + test)
            self.assertEqual(exit, 0, "Error at " + test)

    def test_undefined_element(self):
        p = Program(ElementInstance("Node", "x"))
        try:
            g = generate_graph(p)
        except Exception as e:
            print e.message
            self.assertNotEqual(e.message.find("Element 'Node' is undefined."), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_undefined_element_port(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "x"),
            ElementInstance("Forward", "y"),
            Connect("x","y", "out..."))
        try:
            g = generate_graph(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("Port 'out...' is undefined for element 'x'."), -1,
                                'Expect port undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_undefined_composite_port(self):
        p = Program(
            Forward,
            Composite("Unit", [Port("in", ("x", "in", "extra"))], [Port("out", ("x", "out"))], [], [],
                      Program(
                          ElementInstance("Forward", "x"))),
            CompositeInstance("Unit", "u"))
        try:
            g = generate_graph(p)
        except TypeError as e:
            self.assertNotEqual(e.message.find("should be a pair of (internal instance, port)"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_undefined_composite_port2(self):
        p = Program(
            Forward,
            Composite("Unit", [Port("in", ("x", "in"))], [Port("out", ("x", "out"))], [], [],
                      Program(
                          ElementInstance("Forward", "x"))),
            CompositeInstance("Unit", "u1"),
            CompositeInstance("Unit", "u2"),
            Connect("u1", "u2", "out...")
        )
        try:
            g = generate_graph(p)
        except UndefinedPort as e:
            self.assertNotEqual(e.message.find("Port 'out...' of instance 'u1' is undefined."), -1,
                                'Expect port undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_conflict_output(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            Connect("f1", "f2"),
            Connect("f1", "f3"),
        )
        try:
            g = generate_graph(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("The output port 'out' of element instance 'f1' cannot be connected to both"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_conflict_input(self):
        p = Program(
            Element("Fork",
                    [Port("in", ["int", "int"])],
                    [Port("to_add", ["int", "int"]), Port("to_sub", ["int", "int"])],
                    r'''(int x, int y) = in(); output { to_add(x,y); to_sub(x,y); }'''),
            Element("Add",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); output { out(x+y); }'''),
            Element("Sub",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); output { out(x-y); }'''),
            Element("Print",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [],
                    r'''printf("%d %d\n",in1(), in2());'''),
            ElementInstance("Fork", "Fork"),
            ElementInstance("Add", "Add"),
            ElementInstance("Sub", "Sub"),
            ElementInstance("Print", "Print"),
            Connect("Fork", "Add", "to_add"),
            Connect("Fork", "Sub", "to_sub"),
            Connect("Add", "Print", "out", "in1"),
            Connect("Sub", "Print", "out", "in2"),
            ElementInstance("Sub", "extra"),
            Connect("extra", "Print", "out", "in2")
        )

        try:
            g = generate_graph(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("The input port 'in2' of element instance 'Print' cannot be connected to multiple"), -1)
        else:
            self.fail('Exception is not raised.')


if __name__ == '__main__':
    unittest.main()