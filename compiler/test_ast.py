import unittest
from standard_elements import *
from codegen import *
from join_handling import join_and_resource_annotation_pass


class TestAST(unittest.TestCase):

    def find_roots(self, g):
        return g.find_roots()

    def find_subgraph(self, g, root):
        return g.find_subgraph(root, set())

    def check_api_return(self, g, name_target):
        visit = []
        for name, target in name_target:
            visit.append(name)
            self.assertEqual(target, g.instances[name].API_return)

        for name in g.instances:
            if name not in visit:
                self.assertIsNone(g.instances[name].API_return)

    def check_api_return_final(self, g, names):
        visit = []
        for name in names:
            visit.append(name)
            self.assertIsNotNone(g.instances[name].API_return_final)

        for name in g.instances:
            if name not in visit:
                self.assertIsNone(g.instances[name].API_return_final)

    def check_api_return_from(self, g, name_target):
        visit = []
        for name, target in name_target:
            visit.append(name)
            self.assertEqual([target], g.instances[name].API_return_from)

        for name in g.instances:
            if name not in visit:
                self.assertEqual(g.instances[name].API_return_from, [])

    def test_undefined_element(self):
        p = Program(ElementInstance("Node", "x"))
        try:
            g = program_to_graph_pass(p)
        except Exception as e:
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
            g = program_to_graph_pass(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("Port 'out...' is undefined for element 'x'."), -1,
                                'Expect port undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_pipeline(self):
        p = Program(
            APIFunction("producer", ["int"], None),
            InternalTrigger("consumer"),
            Forward,
            Element("Comsumer", [Port("in", ["int"])], [], r'''printf("%d\n", in());'''),
            ElementInstance("Forward", "Forwarder"),
            ElementInstance("Comsumer", "Comsumer"),
            Connect("Forwarder", "Comsumer"),
            ResourceMap("producer", "Forwarder"),
            ResourceMap("consumer", "Comsumer"),
        )

        g1 = program_to_graph_pass(p)
        g2 = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g2, True, False)

        self.assertEqual(2, len(g1.instances))
        self.assertEqual(4, len(g2.instances))

        root1 = self.find_roots(g1)
        root2 = self.find_roots(g2)

        self.assertEqual(set(["Forwarder"]), root1)
        self.assertEqual(set(["Forwarder", "Comsumer_buffer_read"]), root2)
        self.assertEqual(set(["Forwarder", "Comsumer_buffer_in_write"]),
                         self.find_subgraph(g2, "Forwarder"))
        self.assertEqual(set(["Comsumer_buffer_read", "Comsumer"]),
                         self.find_subgraph(g2, "Comsumer_buffer_read"))

    def test_shared_state(self):
        p = Program(
            State("Shared", "int sum;", "100"),
            Element("Sum", [Port("in", ["int"])], [], r'''this.sum += in(); printf("%d\n", this.sum);''',
                    [("Shared", "this")]),
            StateInstance("Shared", "s"),
            ElementInstance("Sum", "sum1", ["s"]),
            ElementInstance("Sum", "sum2", ["s"])
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)
        self.assertEqual(2, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['sum1', 'sum2']), roots)
        self.assertEqual(set(['s']), set(g.state_instances.keys()))

    def test_nonconflict_input(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            Connect("f1", "f3"),
            Connect("f2", "f3"),
        )
        g = program_to_graph_pass(p)
        self.assertEqual(3, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2']), roots)
        self.assertEqual(set(['f1', 'f3']), self.find_subgraph(g, 'f1'))
        self.assertEqual(set(['f2', 'f3']), self.find_subgraph(g, 'f2'))

    def test_nonconflict_input_thread(self):
        p = Program(
            Forward, Drop,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Drop", "drop"),
            Connect("f1", "drop"),
            Connect("f2", "drop"),
            InternalTrigger("t1"),
            ResourceMap("t1", "drop"),
            InternalTrigger("t2"),
            ResourceMap("t2", "f1"),
            ResourceMap("t2", "f2"),
        )
        try:
            g = program_to_graph_pass(p)
            join_and_resource_annotation_pass(g, True, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("Resource 't2' has more than one starting element instance"),
                                -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_error_both_internal_external(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            APIFunction("api", ["int"], "int"),
            InternalTrigger("t"),
            ResourceMap("api", "f1"),
            ResourceMap("t", "f1"),
        )
        try:
            g = program_to_graph_pass(p)
            join_and_resource_annotation_pass(g, True, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("Element instance 'f1' cannot be mapped to both 'api' and 't'."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_basic_no_output(self):
        p = Program(
            Element("Inc", [Port("in", ["int"])], [Port("out", ["int"])], r'''int x = in() + 1; output { out(x); }'''),
            Element("Print", [Port("in", ["int"])], [], r'''printf("%d\n", in());'''),
            APIFunction("add_and_print", ["int"], None),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Print", "print"),
            Connect("inc1", "print"),
            ResourceMap("add_and_print", "inc1"),
            ResourceMap("add_and_print", "print"),
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)
        self.assertEqual(2, len(g.instances))
        self.assertEqual(0, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['inc1']), roots)
        self.check_api_return(g, [])
        self.check_api_return(g, [])
        self.check_api_return_final(g, [])

    def test_API_blocking_read(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("read", [], "int"),
            ResourceMap("read", "f2"),
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2_buffer_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'f1')))
        self.assertEqual(2, len(self.find_subgraph(g, 'f2_buffer_read')))

        self.check_api_return(g, [("f2_buffer_read", "int"), ("f2", "int")])
        self.check_api_return_from(g, [("f2_buffer_read", "f2")])
        self.check_api_return_final(g, ["f2"])

    def test_API_return_error(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("func", ["int"], None),
            ResourceMap("func", "f1"),
            ResourceMap("func", "f2"),
        )
        try:
            g = program_to_graph_pass(p)
            join_and_resource_annotation_pass(g, True, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("API 'func' should have no return value"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_no_return_okay(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("func", ["int"], None),
            ResourceMap("func", "f1"),
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2_buffer_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'f1')))
        self.assertEqual(2, len(self.find_subgraph(g, 'f2_buffer_read')))

        self.check_api_return(g, [])
        self.check_api_return(g, [])
        self.check_api_return_final(g, [])

    def test_API_return_okay(self):
        p = Program(
            Fork2, Forward, Drop,
            ElementInstance("Fork2", "dup"),
            ElementInstance("Forward", "fwd"),
            ElementInstance("Drop", "drop"),
            Connect("dup", "fwd", "out1"),
            Connect("fwd", "drop"),
            InternalTrigger("t"),
            APIFunction("func", ["int"], "int"),
            ResourceMap("func", "dup"),
            ResourceMap("t", "fwd"),
            ResourceMap("t", "drop"),
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)
        self.assertEqual(5, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['dup', 'fwd_buffer_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'dup')))
        self.assertEqual(3, len(self.find_subgraph(g, 'fwd_buffer_read')))

        self.check_api_return(g, [("dup", "int")])
        self.check_api_return_from(g, [])
        self.check_api_return_final(g, ["dup"])

    def test_API_not_always_return(self):
        p = Program(
            Element("Filter", [Port("in", ["int"])], [Port("out", ["int"])],
                    r'''int x = in(); output switch { case (x>0): out(x); }'''),
            ElementInstance("Filter", "filter"),
            APIFunction("func", ["int"], "int"),
            ResourceMap("func", "filter"),
        )
        try:
            g = program_to_graph_pass(p)
            join_and_resource_annotation_pass(g, True, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("doesn't always return, and the default return value is not provided."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_not_always_return_but_okay(self):
        p = Program(
            Element("Filter", [Port("in", ["int"])], [Port("out", ["int"])],
                    r'''int x = in(); output switch { case (x>0): out(x); }'''),
            ElementInstance("Filter", "filter"),
            APIFunction("func", ["int"], "int", "-1"),
            ResourceMap("func", "filter"),
        )
        g = program_to_graph_pass(p)
        join_and_resource_annotation_pass(g, True, False)


if __name__ == '__main__':
    unittest.main()