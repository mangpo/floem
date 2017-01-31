import unittest
from program import *
from compiler import *


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


    def test_pipeline(self):
        p = Program(
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Comsumer",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            ElementInstance("Forwarder", "Forwarder"),
            ElementInstance("Comsumer", "Comsumer"),
            Connect("Forwarder", "Comsumer")
            , ExternalAPI("Forwarder")
            , InternalThread("Comsumer")
        )

        g1 = generate_graph(p, False)
        g2 = generate_graph(p, True)

        self.assertEqual(2, len(g1.instances))
        self.assertEqual(4, len(g2.instances))

        root1 = self.find_roots(g1)
        root2 = self.find_roots(g2)

        self.assertEqual(set(["Forwarder"]), root1)
        self.assertEqual(set(["Forwarder", "_buffer_Comsumer_read"]), root2)

        for root in root2:
            subgraph = self.find_subgraph(g2, root, set())
            if root == "Forwarder":
                self.assertEqual(set(["Forwarder", "_buffer_Comsumer_in_write"]), subgraph)
            else:
                self.assertEqual(set(["_buffer_Comsumer_read", "Comsumer"]), subgraph)

    def test_join(self):
        p = Program(
            Element("Fork",
                    [Port("in", ["int", "int"])],
                    [Port("to_add", ["int", "int"]), Port("to_sub", ["int", "int"])],
                    r'''(int x, int y) = in(); to_add(x,y); to_sub(x,y);'''),
            Element("Add",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); out(x+y);'''),
            Element("Sub",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); out(x-y);'''),
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
            Connect("Sub", "Print", "out", "in2")
            # , InternalThread("Sub")
        )

        g = generate_graph(p, True)
        self.assertEqual(7, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["Fork"]), roots)

    def test_join_with_threads(self):
        p = Program(
            Element("Fork",
                    [Port("in", ["int", "int"])],
                    [Port("to_add", ["int", "int"]), Port("to_sub", ["int", "int"])],
                    r'''(int x, int y) = in(); to_add(x,y); to_sub(x,y);'''),
            Element("Add",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); out(x+y);'''),
            Element("Sub",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''(int x, int y) = in(); out(x-y);'''),
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
            Connect("Sub", "Print", "out", "in2")
            , InternalThread("Sub")
        )

        g = generate_graph(p, True)
        self.assertEqual(9, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["Fork", "_buffer_Sub_read"]), roots)

        for root in roots:
            subgraph = self.find_subgraph(g, root, set())
            if root == "Fork":
                self.assertEqual(
                    set(['Fork', 'Add', '_buffer_Print_in1_write', '_buffer_Print_read', 'Print',
                         '_buffer_Sub_in_write']),
                    subgraph)
            else:
                self.assertEqual(set(['_buffer_Sub_read', 'Sub', '_buffer_Print_in2_write']), subgraph)

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
                    r'''local.count++; global.count++; out(in());''',
                    None,
                    [("Count", "local"), ("Count", "global")]
                    ),
            Composite("Unit",
                      [Port("in", ("x1", "in"))],
                      [Port("out", ("x2", "out"))],
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
                    r'''this.count++; out(in());''',
                    None,
                    [("Count", "this")]
                    ),
            Element("Print",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            Composite("Unit1",
                      [Port("in", ("x1", "in"))],  # error
                      [Port("out", ("x1", "out"))],
                      [("Count", "c")],
                      Program(
                          ElementInstance("Identity", "x1", ["c"])
                      )),
            Composite("Unit2",
                      [Port("in", ("u1", "in"))],  # error
                      [Port("out", ("u1", "out"))],
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
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Comsumer",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            Composite("Unit", [Port("in", ("Forwarder", "in"))], [Port("out", ("Comsumer", "out"))], [],
                      Program(
                          ElementInstance("Forwarder", "Forwarder"),
                          ElementInstance("Comsumer", "Comsumer"),
                          Connect("Forwarder", "Comsumer"),
                          InternalThread("Comsumer")
                      )),
            CompositeInstance("Unit", "u1"),
            CompositeInstance("Unit", "u2"),
            Connect("u1", "u2")
        )

if __name__ == '__main__':
    unittest.main()