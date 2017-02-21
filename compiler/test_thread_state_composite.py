import unittest
from standard_elements import *
from compiler import *
from desugaring import desugar

class TestThreadStateComposite(unittest.TestCase):

    def find_roots(self, g):
        """
        :return: roots of the graph (elements that have no parent)
        """
        instances = g.instances
        not_roots = set()
        for name in instances:
            instance = instances[name]
            for (next, port) in instance.output2ele.values():
                not_roots.add(next)

        roots = set(instances.keys()).difference(not_roots)
        return roots

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

    def test_pipeline(self):
        p = Program(
            Forward,
            Element("Comsumer",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            ElementInstance("Forward", "Forwarder"),
            ElementInstance("Comsumer", "Comsumer"),
            Connect("Forwarder", "Comsumer")
            , ExternalTrigger("Forwarder")
            , InternalTrigger("Comsumer")
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

    def test_composite(self):
        p = Program(
            State("Count", "int count;", "0"),
            Element("Identity",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''local.count++; global.count++; int x = in(); output { out(x); }''',
                    None,
                    [("Count", "local"), ("Count", "global")]
                    ),
            Composite("Unit",
                      [Port("in", ("x1", "in"))],
                      [Port("out", ("x2", "out"))], [],
                      [("Count", "global")],
                      Program(
                          StateInstance("Count", "local"),
                          ElementInstance("Identity", "x1", ["local", "global"]),
                          ElementInstance("Identity", "x2", ["local", "global"]),
                          Connect("x1", "x2")  # error
                          # , InternalThread("x2")
                      )),
            StateInstance("Count", "c"),
            Element("Print",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            CompositeInstance("Unit", "u1", ["c"]),
            CompositeInstance("Unit", "u2", ["c"]),
            ElementInstance("Print", "Print"),
            Connect("u1", "u2"),
            Connect("u2", "Print")
        )
        g = generate_graph(p, True)
        self.assertEqual(9, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['u1_in']), roots)
        self.assertEqual(set(['c', '_u1_local', '_u2_local']), set(g.state_instances.keys()))

    def test_nested_composite(self):
        p = Program(
            State("Count", "int count;", "0"),
            Element("Identity",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''this.count++; int x = in(); output { out(x); }''',
                    None,
                    [("Count", "this")]
                    ),
            Element("Print",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            Composite("Unit1",
                      [Port("in", ("x1", "in"))],  # error
                      [Port("out", ("x1", "out"))], [],
                      [("Count", "c")],
                      Program(
                          ElementInstance("Identity", "x1", ["c"])
                      )),
            Composite("Unit2",
                      [Port("in", ("u1", "in"))],  # error
                      [Port("out", ("u1", "out"))], [],
                      [("Count", "c1")],
                      Program(
                          CompositeInstance("Unit1", "u1", ["c1"])
                      )),
            StateInstance("Count", "c2"),
            CompositeInstance("Unit2", "u2", ["c2"]),
            ElementInstance("Print", "Print"),
            Connect("u2", "Print")
        )

        g = generate_graph(p, True)
        self.assertEqual(6, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['u2_in']), roots)
        self.assertEqual(set(['c2']), set(g.state_instances.keys()))
        self.assertEqual(set(g.instances.keys()), self.find_subgraph(g, 'u2_in', set()))

    def test_composite_with_threads(self):

        p = Program(
            Forward,
            Composite("Unit", [Port("in", ("f1", "in"))], [Port("out", ("f2", "out"))], [], [],
                      Program(
                          ElementInstance("Forward", "f1"),
                          ElementInstance("Forward", "f2"),
                          Connect("f1", "f2"),
                          InternalTrigger("f2")
                      )),
            CompositeInstance("Unit", "u1"),
            CompositeInstance("Unit", "u2"),
            Connect("u1", "u2")
        )
        g = generate_graph(p, True)
        self.assertEqual(12, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['u1_in', '_buffer__u1_f2_read', '_buffer__u2_f2_read']), roots)

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
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            Connect("f1", "f3"),
            Connect("f2", "f3"),
            InternalTrigger("f3")
        )
        g = generate_graph(p)
        self.assertEqual(5, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2', '_buffer_f3_read']), roots)
        self.assertEqual(set(['f1', '_buffer_f3_in_write']), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(['f2', '_buffer_f3_in_write']), self.find_subgraph(g, 'f2', set()))
        self.assertEqual(set(['_buffer_f3_read', 'f3']), self.find_subgraph(g, '_buffer_f3_read', set()))

    def test_error_both_internal_external(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ExternalTrigger("f1"),
            InternalTrigger("f1")
        )
        try:
            g = generate_graph(p)
        except Exception as e:
            self.assertNotEqual(e.message.find("cannot be triggered by both internal and external triggers"), -1)
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
            APIFunction2("add_and_print", ["int"], None),
            ElementInstance("Inc", "inc1", [], "add_and_print", True),
            ElementInstance("Print", "print", [], "add_and_print"),
            Connect("inc1", "print"),
            #ResourceMap("add_and_print", "inc1", True),
            #ResourceMap("add_and_print", "print"),
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
            APIFunction2("read", [], "int"),
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
            APIFunction2("func", ["int"], None),
            ResourceMap("func", "f1", True),
            ResourceMap("func", "f2"),
        )
        try:
            g = generate_graph(p)
        except Exception as e:
            print e.message
            self.assertNotEqual(e.message.find("API 'func' should have no return value"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_no_return_okay(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction2("func", ["int"], None),
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
            Fork2, Forward,
            ElementInstance("Fork2", "dup"),
            ElementInstance("Forward", "fwd"),
            Connect("dup", "fwd", "out1"),
            InternalTrigger("fwd"),
            APIFunction("func", "dup", "in", "dup", "out2", "int"),
            APIFunction2("func", ["int"], "int"),
            ResourceMap("func", "dup", True),
            #InternalTrigger2("t"),
            #ResourceMap("t", "fwd", True),
        )
        g = generate_graph(p)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['dup', '_buffer_fwd_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'dup', set())))
        self.assertEqual(2, len(self.find_subgraph(g, '_buffer_fwd_read', set())))

        self.check_api_return(g, [("dup", "int")])
        self.check_api_return_from(g, [])
        self.check_api_return_final(g, ["dup"])

    # TODO
    def test_API_not_always_return(self):
        p = Program(
            Inc, CircularQueue("Queue", "int", 4),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Inc", "inc2"),
            CompositeInstance("Queue", "queue"),
            Inject("int", "inject", 8, "gen_func"),

            Connect("inject", "inc1"),
            Connect("inc1", "queue"),
            Connect("queue", "inc2"),
            APIFunction("dequeue", "queue", "dequeue", "inc2", "out", "int"),
        )
        try:
            g = generate_graph(desugar(p))
        except Exception as e:
            self.assertNotEqual(e.message.find("doesn't always return, and the default return value is not provided."), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    # TODO
    def test_API_not_always_return_but_okay(self):
        p = Program(
            Inc, CircularQueue("Queue", "int", 4),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Inc", "inc2"),
            CompositeInstance("Queue", "queue"),
            Inject("int", "inject", 8, "gen_func"),

            Connect("inject", "inc1"),
            Connect("inc1", "queue"),
            Connect("queue", "inc2"),
            APIFunction("dequeue", "queue", "dequeue", "inc2", "out", "int", -1)
        )
        g = generate_graph(desugar(p))

    def test_composite_scope(self):
        p = Program(
            Forward,
            Composite("Unit1",
                      [Port("in", ("aa", "in"))],
                      [Port("out", ("aa", "out"))],
                      [],
                      [],
                      Program(
                          ElementInstance("Forward", "aa")
                      )),
            Composite("Unit2",
                      [Port("in", ("bb", "in"))],
                      [Port("out", ("cc", "out"))],
                      [],
                      [],
                      Program(
                          ElementInstance("Forward", "bb"),
                          ElementInstance("Forward", "cc"),
                          Connect("bb", "cc")
                      )),
            Composite("Wrapper1",
                      [Port("in", ("u", "in"))],
                      [Port("out", ("u", "out"))],
                      [],
                      [],
                      Program(
                          CompositeInstance("Unit1", "u")
                      )),
            CompositeInstance("Wrapper1", "u"),
            Composite("Wrapper2",
                      [Port("in", ("u", "in"))],
                      [Port("out", ("u", "out"))],
                      [],
                      [],
                      Program(
                          CompositeInstance("Unit2", "u")
                      )),
            CompositeInstance("Wrapper2", "w2"),
            Connect("u", "w2")
        )

        g = generate_graph(p)
        roots = self.find_roots(g)
        self.assertEqual(set(['u_in']), roots)
        self.assertEqual(11, len(self.find_subgraph(g, 'u_in', set())))


if __name__ == '__main__':
    unittest.main()