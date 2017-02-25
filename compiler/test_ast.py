import unittest
from standard_elements import *
from compiler import *
from desugaring import desugar


class TestAST(unittest.TestCase):

    def find_roots(self, g):
        return g.find_roots()

    def find_subgraph(self, g, root, subgraph):
        instance = g.instances[root]
        if instance.name not in subgraph:
            subgraph.add(instance.name)
            for ele,port in instance.output2ele.values():
                self.find_subgraph(g, ele, subgraph)
        return subgraph

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
            self.assertEqual(target, g.instances[name].API_return_from)

        for name in g.instances:
            if name not in visit:
                self.assertIsNone(g.instances[name].API_return_from)

    def test_undefined_element(self):
        p = Program(ElementInstance("Node", "x"))
        try:
            g = generate_graph(p)
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
            g = generate_graph(p)
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
            Element("Comsumer",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            ElementInstance("Forward", "Forwarder"),
            ElementInstance("Comsumer", "Comsumer"),
            Connect("Forwarder", "Comsumer"),
            ResourceMap("producer", "Forwarder", True),
            ResourceMap("consumer", "Comsumer", True)
        )

        g1 = generate_graph(p, False)
        g2 = generate_graph(p, True)

        self.assertEqual(2, len(g1.instances))
        self.assertEqual(4, len(g2.instances))

        root1 = self.find_roots(g1)
        root2 = self.find_roots(g2)

        self.assertEqual(set(["Forwarder"]), root1)
        self.assertEqual(set(["Forwarder", "_buffer_Comsumer_read"]), root2)
        self.assertEqual(set(["Forwarder", "_buffer_Comsumer_in_write"]),
                         self.find_subgraph(g2, "Forwarder", set()))
        self.assertEqual(set(["_buffer_Comsumer_read", "Comsumer"]),
                         self.find_subgraph(g2, "_buffer_Comsumer_read", set()))

    def test_shared_state(self):
        p = Program(
            State("Shared", "int sum;", "100"),
            Element("Sum",
                    [Port("in", ["int"])],
                    [],
                    r'''this.sum += in(); printf("%d\n", this.sum);''',
                    None,
                    [("Shared", "this")]),
            StateInstance("Shared", "s"),
            ElementInstance("Sum", "sum1", ["s"]),
            ElementInstance("Sum", "sum2", ["s"])
        )
        g = generate_graph(p, True)
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
        g = generate_graph(p)
        self.assertEqual(3, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2']), roots)
        self.assertEqual(set(['f1', 'f3']), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(['f2', 'f3']), self.find_subgraph(g, 'f2', set()))

    def test_nonconflict_input_thread(self):
        p = Program(
            Forward, Drop,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Drop", "drop"),
            Connect("f1", "drop"),
            Connect("f2", "drop"),
            InternalTrigger("t"),
            ResourceMap("t", "drop", True)
        )
        g = generate_graph(p)
        self.assertEqual(5, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2', '_buffer_drop_read']), roots)
        self.assertEqual(set(['f1', '_buffer_drop_in_write']), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(['f2', '_buffer_drop_in_write']), self.find_subgraph(g, 'f2', set()))
        self.assertEqual(set(['_buffer_drop_read', 'drop']), self.find_subgraph(g, '_buffer_drop_read', set()))

    def test_error_both_internal_external(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            APIFunction("api", ["int"], "int"),
            InternalTrigger("t"),
            ResourceMap("api", "f1", True),
            ResourceMap("t", "f1", True),
        )
        try:
            g = generate_graph(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("Element instance 'f1' cannot be mapped to both 'api' and 't'."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_basic_no_output(self):
        p = Program(
            Element("Inc",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in() + 1; output { out(x); }'''),
            Element("Print",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            APIFunction("add_and_print", ["int"], None),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Print", "print"),
            Connect("inc1", "print"),
            ResourceMap("add_and_print", "inc1", True),
            ResourceMap("add_and_print", "print"),
        )
        g = generate_graph(p)
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
            ResourceMap("read", "f2", True),
        )
        g = generate_graph(p)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', '_buffer_f2_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'f1', set())))
        self.assertEqual(2, len(self.find_subgraph(g, '_buffer_f2_read', set())))

        self.check_api_return(g, [("_buffer_f2_read", "int"), ("f2", "int")])
        self.check_api_return_from(g, [("_buffer_f2_read", "f2")])
        self.check_api_return_final(g, ["f2"])

    def test_API_return_error(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("func", ["int"], None),
            ResourceMap("func", "f1", True),
            ResourceMap("func", "f2"),
        )
        try:
            g = generate_graph(p)
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
            ResourceMap("func", "f1", True),
        )
        g = generate_graph(p)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', '_buffer_f2_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'f1', set())))
        self.assertEqual(2, len(self.find_subgraph(g, '_buffer_f2_read', set())))

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
            ResourceMap("func", "dup", True),
            ResourceMap("t", "fwd", True),
            ResourceMap("t", "drop", False),
        )
        g = generate_graph(p)
        self.assertEqual(5, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['dup', '_buffer_fwd_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'dup', set())))
        self.assertEqual(3, len(self.find_subgraph(g, '_buffer_fwd_read', set())))

        self.check_api_return(g, [("dup", "int")])
        self.check_api_return_from(g, [])
        self.check_api_return_final(g, ["dup"])

    def test_API_not_always_return(self):
        p = Program(
            Element("Filter",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in(); output switch { case (x>0): out(x); }'''),
            ElementInstance("Filter", "filter"),
            APIFunction("func", ["int"], "int"),
            ResourceMap("func", "filter", True)
        )
        try:
            g = generate_graph(desugar(p))
        except Exception as e:
            self.assertNotEqual(e.message.find("doesn't always return, and the default return value is not provided."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_not_always_return_but_okay(self):
        p = Program(
            Element("Filter",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in(); output switch { case (x>0): out(x); }'''),
            ElementInstance("Filter", "filter"),
            APIFunction("func", ["int"], "int", "-1"),
            ResourceMap("func", "filter", True)
        )
        g = generate_graph(desugar(p))


if __name__ == '__main__':
    unittest.main()