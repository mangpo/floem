from standard_elements import *
from compiler import *
from join_handling import InstancePart, FlowCollection
import unittest


class TestJoinHandling(unittest.TestCase):

    def test_InstancePart(self):
        x1 = InstancePart("x", set([0, 1, 2]), 5)
        x2 = InstancePart("x", set([3, 4]), 5)
        x3 = InstancePart("x", set([2, 3]), 5)

        y1 = x1.union(x2)
        y2 = x1. union(x3)
        self.assertEqual(y1, "x")
        self.assertEqual(y2, InstancePart("x", set([0, 1, 2, 3]), 5))

        z1 = x1.intersection(x2)
        z2 = x1.intersection(x3)
        self.assertEqual(z1, False)
        self.assertEqual(z2, InstancePart("x", set([2]), 5))

    def test_FlowCollection(self):
        c1 = FlowCollection("x", 2, 0)
        c2 = FlowCollection("x", 2, 1)

        d1 = c1.intersection(c2)
        self.assertTrue(d1.empty())

        d2 = c1.union(c2)
        self.assertEqual(d2.collection, ["x"])

    def test_FlowCollection2(self):
        c1 = FlowCollection("x", 3, [[InstancePart("x", set([0,1]), 3)]], False)
        c2 = FlowCollection("x", 3, [[InstancePart("x", set([2]), 3)]], False)
        c3 = FlowCollection("x", 3, [[InstancePart("x", set([1,2]), 3)]], False)
        c4 = FlowCollection("x", 3, [[InstancePart("x", set([0]), 3)]], False)

        d1 = c1.intersection(c2)
        d2 = c1.intersection(c3)
        self.assertEqual(d1.collection, [])
        self.assertTrue(d1.empty())
        self.assertEqual(d2.collection, [[InstancePart("x", set([1]), 3)]], str(d2))

        u1 = c1.union(c2)
        self.assertEqual(u1.collection, ["x"])

        u2 = c2.union(c4)
        self.assertEqual(u2.collection, [[InstancePart("x", set([0,2]), 3)]], str(u2))

        try:
            u3 = c2.union(c3)
        except Exception as e:
            self.assertNotEqual(e.message.find("is fired more than once"), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_FlowCollection3(self):
        c1 = FlowCollection("y", 3, [[InstancePart("y", set([0]), 2), InstancePart("x", set([0,1]), 3)]], False)
        c2 = FlowCollection("y", 3, [[InstancePart("y", set([0]), 2), InstancePart("x", set([2]), 3)]], False)
        u1 = c1.union(c2)
        self.assertEqual(u1.collection, [[InstancePart("y", set([0]), 2)]])

        c3 = FlowCollection("y", 3, [[InstancePart("y", set([1]), 2), InstancePart("x", set([0]), 3)]], False)
        c4 = FlowCollection("y", 3, [[InstancePart("y", set([1]), 2), InstancePart("x", set([1,2]), 3)]], False)
        u2 = c3.union(c4)
        self.assertEqual(u2.collection, [[InstancePart("y", set([1]), 2)]])

        u = u1.union(u2)
        self.assertEqual(u.collection, ["y"])

        u1 = c1.union(c3)
        u2 = c2.union(c4)
        self.assertEqual(u1.collection, [[InstancePart("y", set([0]), 2), InstancePart("x", set([0, 1]), 3)],
                                         [InstancePart("y", set([1]), 2), InstancePart("x", set([0]), 3)]])
        self.assertEqual(u2.collection, [[InstancePart("y", set([0]), 2), InstancePart("x", set([2]), 3)],
                                         [InstancePart("y", set([1]), 2), InstancePart("x", set([1, 2]), 3)]])
        u = u1.union(c2)
        self.assertEqual(u.collection, [[InstancePart("y", set([1]), 2), InstancePart("x", set([0]), 3)],
                                        [InstancePart("y", set([0]), 2)]])

        u = u1.union(u2)
        self.assertEqual(u.collection, ["y"])
        self.assertTrue(u.full())

    def test_append(self):
        c1 = FlowCollection("x", 3, [[InstancePart("x", set([0, 1]), 3)]], False)
        c2 = c1.clone()
        c3 = c1.clone()
        c2.append(InstancePart("y", set([0]), 2))
        c3.append(InstancePart("y", set([1]), 2))

        self.assertEqual(c2.collection, [[InstancePart("x", set([0, 1]), 3), InstancePart("y", set([0]), 2)]], str(c2))
        self.assertEqual(c3.collection, [[InstancePart("x", set([0, 1]), 3), InstancePart("y", set([1]), 2)]], str(c3))


        c1 = FlowCollection("x", 3, [[InstancePart("x", set([0]), 3)], [InstancePart("x", set([2]), 3)]], False)
        c2 = c1.clone()
        c2.append(InstancePart("y", set([0]), 2))
        self.assertEqual(c2.collection, [[InstancePart("x", set([0]), 3), InstancePart("y", set([0]), 2)],
                                         [InstancePart("x", set([2]), 3), InstancePart("y", set([0]), 2)]],
                         str(c2))


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

    def check_join_ports_same_thread(self, g, name_ports):
        visit = []
        for name, ports in name_ports:
            visit.append(name)
            self.assertEqual(set(ports), set([port.name for port in g.instances[name].join_ports_same_thread]))

        for name in g.instances:
            if name not in visit:
                self.assertIsNone(g.instances[name].join_ports_same_thread)

    def check_join_state_create(self, g, name_creates):
        visit = []
        for name, targets in name_creates:
            visit.append(name)
            self.assertEqual(set(targets), set(g.instances[name].join_state_create))

        for name in g.instances:
            if name not in visit:
                self.assertEqual([], g.instances[name].join_state_create)

    def check_join_call(self, g, name_calls):
        visit = []
        for name, targets in name_calls:
            visit.append(name)
            self.assertEqual(set(targets), set(g.instances[name].join_call))

        for name in g.instances:
            if name not in visit:
                self.assertEqual([], g.instances[name].join_call)

    def test_fork_join(self):
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
            Connect("Sub", "Print", "out", "in2")
            # , InternalThread("Sub")
        )

        g = generate_graph(p, False)
        self.assertEqual(4, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["Fork"]), roots)

        self.check_join_ports_same_thread(g, [("Print", ["in1", "in2"])])
        self.check_join_state_create(g, [("Fork", ["Print"])])

        self.assertEqual(g.instances["Fork"].join_func_params, [])
        self.assertEqual(g.instances["Add"].join_func_params, ["Print"])
        self.assertEqual(g.instances["Sub"].join_func_params, ["Print"])
        self.assertEqual(g.instances["Print"].join_func_params, [])

        self.assertEqual(g.instances["Fork"].join_output2save, {})
        self.assertEqual(g.instances["Add"].join_output2save, {'out': 'Print'})
        self.assertEqual(g.instances["Sub"].join_output2save, {'out': 'Print'})
        self.assertEqual(g.instances["Print"].join_output2save, {})

        self.check_join_call(g, [("Sub", ["Print"])])

    def test_fork_join_thread1(self):
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
            InternalTrigger("t"),
            ResourceMap("t", "Print"),
        )

        g = generate_graph(p, False)
        self.assertEqual(4, len(g.instances))

        g = generate_graph(p, True)
        self.assertEqual(7, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['Fork', 'Print_buffer_read']), roots)
        self.assertEqual(set(['Fork', 'Add', 'Print_buffer_in1_write', 'Sub', 'Print_buffer_in2_write']),
                         self.find_subgraph(g, 'Fork', set()))
        self.assertEqual(set(['Print_buffer_read', 'Print']),
                         self.find_subgraph(g, 'Print_buffer_read', set()))

        self.check_join_ports_same_thread(g, [])
        self.check_join_state_create(g, [])
        self.check_join_call(g, [])

    def test_fork_join_thread2(self):
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
            InternalTrigger("t"),
            ResourceMap("t", "Sub"),
        )

        g = generate_graph(p, False)
        self.assertEqual(4, len(g.instances))

        g = generate_graph(p, True)
        self.assertEqual(8, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['Fork', 'Sub_buffer_read']), roots)
        self.assertEqual(5, len(self.find_subgraph(g, 'Fork', set())))
        self.assertEqual(3, len(self.find_subgraph(g, 'Sub_buffer_read', set())))

        self.check_join_ports_same_thread(g, [])
        self.check_join_state_create(g, [])
        self.check_join_call(g, [])

    def test_fork_join_half(self):
        p = Program(
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in(); output { out(x); }'''),
            Element("Print",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [],
                    r'''printf("%d %d\n",in1(), in2());'''),
            ElementInstance("Forwarder", "f1"),
            ElementInstance("Forwarder", "f2"),
            ElementInstance("Print", "Print"),
            Connect("f1", "Print", "out", "in1"),
            Connect("f2", "Print", "out", "in2"),
            APIFunction("run", ["int"], None),
            ResourceMap("run", "f2"),
        )

        try:
            g = generate_graph(p, False)
            generate_code(g)
        except Exception as e:
            self.assertNotEqual(e.message.find("There is no dominant element instance"), -1)
        else:
            self.fail('Exception is not raised.')

        g = generate_graph(p, True)
        self.assertEqual(5, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["f1", "f2"]), roots)
        self.assertEqual(set(["f1", 'Print_buffer_read', "Print"]), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(["f2", 'Print_buffer_in2_write']), self.find_subgraph(g, 'f2', set()))
        self.check_join_ports_same_thread(g, [])

    def test_join_only(self):
        p = Program(
            Element("Print",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [],
                    r'''printf("%d %d\n",in1(), in2());'''),
            ElementInstance("Print", "Print")
        )

        g = generate_graph(p, True)
        self.assertEqual(1, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["Print"]), roots)
        self.check_join_ports_same_thread(g, [])

    def test_multi_joins(self):
        p = Program(
            Fork2, Fork3, Forward, Add,
            ElementInstance("Fork3", "fork3"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork3", "f1", "out1"),
            Connect("fork3", "fork2", "out2"),
            Connect("fork3", "f2", "out3"),
            Connect("fork2", "add1", "out1", "in1"),
            Connect("fork2", "add2", "out2", "in1"),
            Connect("f1", "add1", "out", "in2"),
            Connect("f2", "add2", "out", "in2")
        )

        g = generate_graph(p, False)
        self.assertEqual(6, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["fork3"]), roots)

        self.check_join_ports_same_thread(g, [("add1", ["in1", "in2"]), ("add2", ["in1", "in2"])])
        self.check_join_state_create(g, [("fork3", ["add1", "add2"])])

        self.assertEqual(g.instances["fork3"].join_func_params, [])
        self.assertEqual(set(g.instances["fork2"].join_func_params), set(["add1", "add2"]))
        self.assertEqual(g.instances["f1"].join_func_params, ["add1"])
        self.assertEqual(g.instances["f2"].join_func_params, ["add2"])
        self.assertEqual(g.instances["add1"].join_func_params, [])
        self.assertEqual(g.instances["add2"].join_func_params, [])

        self.assertEqual(g.instances["fork3"].join_output2save, {})
        self.assertEqual(g.instances["fork2"].join_output2save, {'out1': 'add1', 'out2': 'add2'})
        self.assertEqual(g.instances["f1"].join_output2save, {'out': 'add1'})
        self.assertEqual(g.instances["f2"].join_output2save, {'out': 'add2'})
        self.assertEqual(g.instances["add1"].join_output2save, {})
        self.assertEqual(g.instances["add2"].join_output2save, {})

        self.check_join_call(g, [("f1", ["add1"]), ("f2", ["add2"])])

        self.assertEqual(g.instances["fork3"].join_partial_order, ['out2', 'out1', 'out3'])
        self.assertEqual(g.instances["fork2"].join_partial_order, [])
        self.assertEqual(g.instances["f1"].join_partial_order, [])
        self.assertEqual(g.instances["f2"].join_partial_order, [])
        self.assertEqual(g.instances["add1"].join_partial_order, [])
        self.assertEqual(g.instances["add2"].join_partial_order, [])

    def test_nested_joins(self):
        p = Program(
            Fork2, Forward, Add,
            ElementInstance("Fork2", "fork1"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork1", "fork2", "out2"),
            Connect("fork1", "f3", "out1"),
            Connect("fork2", "f1", "out1"),
            Connect("fork2", "f2", "out2"),
            Connect("f1", "add1", "out", "in1"),
            Connect("f2", "add1", "out", "in2"),
            Connect("add1", "add2", "out", "in1"),
            Connect("f3", "add2", "out", "in2")
        )

        g = generate_graph(p, False)
        self.assertEqual(7, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["fork1"]), roots)

        self.check_join_ports_same_thread(g, [("add1", ["in1", "in2"]), ("add2", ["in1", "in2"])])
        self.check_join_state_create(g, [("fork2", ["add1"]), ("fork1", ["add2"])])

        self.assertEqual(g.instances["fork1"].join_func_params, [])
        self.assertEqual(g.instances["fork2"].join_func_params, ["add2"])
        self.assertEqual(g.instances["f3"].join_func_params, ["add2"])
        self.assertEqual(set(g.instances["f1"].join_func_params), set(["add1", "add2"]))
        self.assertEqual(set(g.instances["f2"].join_func_params), set(["add1", "add2"]))
        self.assertEqual(g.instances["add1"].join_func_params, ["add2"])
        self.assertEqual(g.instances["add2"].join_func_params, [])

        self.assertEqual(g.instances["fork1"].join_output2save, {})
        self.assertEqual(g.instances["fork2"].join_output2save, {})
        self.assertEqual(g.instances["f1"].join_output2save, {'out': 'add1'})
        self.assertEqual(g.instances["f2"].join_output2save, {'out': 'add1'})
        self.assertEqual(g.instances["add1"].join_output2save, {'out': 'add2'})
        self.assertEqual(g.instances["f3"].join_output2save, {'out': 'add2'})
        self.assertEqual(g.instances["add2"].join_output2save, {})

        self.check_join_call(g, [("f2", ["add1"]), ("f3", ["add2"])])

        self.assertEqual(g.instances["fork1"].join_partial_order, ["out2", "out1"])
        self.assertEqual(g.instances["fork2"].join_partial_order, ["out1", "out2"])

    def test_join_error(self):
        p = Program(
            Fork2, Forward, Add,
            ElementInstance("Fork2", "fork1"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add1"),
            Connect("fork1", "f1", "out1"),
            Connect("fork1", "fork2", "out2"),
            Connect("fork2", "f2", "out1"),
            Connect("fork2", "f3", "out2"),
            Connect("f1", "add1", "out", "in1"),
            Connect("f2", "add1", "out", "in2"),
            Connect("f3", "add1", "out", "in2")
        )
        try:
            g = generate_graph(p, True)
        except Exception as e:
            self.assertNotEqual(e.message.find("Element instance 'fork2' fires port"), -1)
            self.assertNotEqual(e.message.find("of the join instance 'add1' more than once"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_join_both_both(self):
        p = Program(
            Fork2, Forward, Add,
            ElementInstance("Fork2", "a"),
            ElementInstance("Fork2", "b1"),
            ElementInstance("Fork2", "b2"),
            ElementInstance("Forward", "c1"),
            ElementInstance("Forward", "c2"),
            ElementInstance("Add", "d"),
            Connect("a", "b1", "out1"),
            Connect("a", "b2", "out2"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c2", "out1"),
            Connect("b2", "c1", "out2"),
            Connect("c1", "d", "out", "in1"),
            Connect("c2", "d", "out", "in2"),
        )

        g = generate_graph(p, False)
        self.assertEqual(6, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["a"]), roots)

        self.check_join_ports_same_thread(g, [("d", ["in1", "in2"])])
        self.check_join_state_create(g, [("b1", ["d"]), ("b2", ["d"])])

        self.assertEqual(g.instances["a"].join_partial_order, [])
        self.assertEqual(g.instances["b1"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["b2"].join_partial_order, ["out2", "out1"])
        self.assertEqual(g.instances["c1"].join_partial_order, [])
        self.assertEqual(g.instances["c2"].join_partial_order, [])
        self.assertEqual(g.instances["d"].join_partial_order, [])

    def test_join_either_both(self):
        p = Program(
            Element("Choice",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''output switch { case x < 0: out1(x); else: out2(x); }'''),
            Fork2, Forward, Add,
            ElementInstance("Choice", "a"),
            ElementInstance("Fork2", "b1"),
            ElementInstance("Fork2", "b2"),
            ElementInstance("Forward", "c1"),
            ElementInstance("Forward", "c2"),
            ElementInstance("Add", "d"),
            Connect("a", "b1", "out1"),
            Connect("a", "b2", "out2"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c2", "out1"),
            Connect("b2", "c1", "out2"),
            Connect("c1", "d", "out", "in1"),
            Connect("c2", "d", "out", "in2"),
        )

        g = generate_graph(p, False)
        self.assertEqual(6, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["a"]), roots)

        self.check_join_ports_same_thread(g, [("d", ["in1", "in2"])])
        self.check_join_state_create(g, [("b1", ["d"]), ("b2", ["d"])])

        self.assertEqual(g.instances["a"].join_partial_order, [])
        self.assertEqual(g.instances["b1"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["b2"].join_partial_order, ["out2", "out1"])
        self.assertEqual(g.instances["c1"].join_partial_order, [])
        self.assertEqual(g.instances["c2"].join_partial_order, [])
        self.assertEqual(g.instances["d"].join_partial_order, [])

    def test_join_both_either_error(self):
        p = Program(
            Element("Choice",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''output switch { case x < 0: out1(x); else: out2(x); }'''),
            Fork2, Forward, Add,
            ElementInstance("Fork2", "a"),
            ElementInstance("Choice", "b1"),
            ElementInstance("Choice", "b2"),
            ElementInstance("Forward", "c1"),
            ElementInstance("Forward", "c2"),
            ElementInstance("Add", "d"),
            Connect("a", "b1", "out1"),
            Connect("a", "b2", "out2"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c2", "out1"),
            Connect("b2", "c1", "out2"),
            Connect("c1", "d", "out", "in1"),
            Connect("c2", "d", "out", "in2"),
        )

        try:
            g = generate_graph(p, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("All its output ports must fire the same input ports of the join instance 'd'."),
                                -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_join_both_both_order(self):
        p = Program(
            Fork2, Forward, Add,
            Element("Fork4",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"]), Port("out3", ["int"]), Port("out4", ["int"])],
                    r'''int x = in(); output { out1(x); out2(x); out3(x); out4(x); }'''),
            ElementInstance("Fork4", "a"),
            ElementInstance("Fork2", "b1"),
            ElementInstance("Fork2", "b2"),
            ElementInstance("Forward", "c1"),
            ElementInstance("Forward", "c2"),
            ElementInstance("Add", "d"),
            Connect("a", "b1", "out2"),
            Connect("a", "b2", "out3"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c1", "out1"),
            Connect("b2", "c2", "out2"),
            Connect("c1", "d", "out", "in1"),
            Connect("c2", "d", "out", "in2"),
            Connect("a", "c1", "out1"),
            Connect("a", "c2", "out4")
        )

        g = generate_graph(p, False)

        self.check_join_ports_same_thread(g, [("d", ["in1", "in2"])])
        self.check_join_state_create(g, [("b1", ["d"]), ("b2", ["d"]),("a", ["d"])])

        self.assertEqual(g.instances["a"].join_partial_order, ["out2", "out3", "out1", "out4"])
        self.assertEqual(g.instances["b1"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["b2"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["c1"].join_partial_order, [])
        self.assertEqual(g.instances["c2"].join_partial_order, [])
        self.assertEqual(g.instances["d"].join_partial_order, [])

    def test_join_uneven(self):
        p = Program(
            Fork2, Forward, Add,
            ElementInstance("Fork2", "fork1"),
            ElementInstance("Forward", "f"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork1", "f", "out1"),
            Connect("fork1", "fork2", "out2"),
            Connect("f", "add1", "out", "in1"),
            Connect("fork2", "add1", "out1", "in2"),
            Connect("add1", "add2", "out", "in1"),
            Connect("fork2", "add2", "out2", "in2"),
        )

        g = generate_graph(p, False)

        self.check_join_ports_same_thread(g, [("add1", ["in1", "in2"]), ("add2", ["in1", "in2"])])
        self.check_join_state_create(g, [("fork1", ["add1", "add2"])])

        self.assertEqual(g.instances["fork1"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["fork2"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["f"].join_partial_order, [])
        self.assertEqual(g.instances["add1"].join_partial_order, [])
        self.assertEqual(g.instances["add2"].join_partial_order, [])

    def test_join_order(self):
        p = Program(
            Fork2, Fork3, Forward, Add,
            Element("Add3",
                    [Port("in1", ["int"]), Port("in2", ["int"]), Port("in3", ["int"])],
                    [],
                    r'''int x = in1() + in2() + in3();'''),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Fork3", "fork3"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add2"),
            ElementInstance("Add3", "add3"),
            Connect("fork2", "f1", "out1"),
            Connect("fork2", "fork3", "out2"),
            Connect("fork3", "f2", "out3"),
            Connect("fork3", "f3", "out2"),
            Connect("f2", "add2", "out", "in1"),
            Connect("f3", "add2", "out", "in2"),
            Connect("f1", "add3", "out", "in1"),
            Connect("add2", "add3", "out", "in2"),
            Connect("fork3", "add3", "out1", "in3"),
        )

        g = generate_graph(p, False)

        self.check_join_ports_same_thread(g, [("add2", ["in1", "in2"]), ("add3", ["in1", "in2", "in3"])])
        self.check_join_state_create(g, [("fork2", ["add3"]), ("fork3", ["add2"])])

        self.assertEqual(g.instances["fork2"].join_partial_order, ["out1", "out2"])
        self.assertEqual(g.instances["fork3"].join_partial_order, ["out3", "out2", "out1"])

    def test_nested_join_thread(self):
        p = Program(
            Forward, Add,
            Element("Fork4",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"]), Port("out3", ["int"]), Port("out4", ["int"])],
                    r'''int x = in(); output { out1(x); out2(x); out3(x); out4(x); }'''),
            Element("Add3",
                    [Port("in1", ["int"]), Port("in2", ["int"]), Port("in3", ["int"])],
                    [Port("out", ["int"])],
                    r'''int x = in1() + in2() + in3(); output { out(x); }'''),
            ElementInstance("Fork4", "fork4"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add3", "add3"),
            ElementInstance("Add", "add2"),
            Connect("fork4", "f1", "out1"),
            Connect("fork4", "f2", "out2"),
            Connect("fork4", "f3", "out3"),
            Connect("f1", "add3", "out", "in1"),
            Connect("f2", "add3", "out", "in2"),
            Connect("f3", "add3", "out", "in3"),
            Connect("add3", "add2", "out", "in1"),
            Connect("fork4", "add2", "out4", "in2"),
            InternalTrigger("t"),
            ResourceMap("t", "f3"),
        )

        g = generate_graph(p, True)
        self.assertEqual(10, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['fork4', 'f3_buffer_read']), roots)

        self.check_join_ports_same_thread(g, [('add3_buffer_read', ["in1", "in2"]), ("add2", ["in1", "in2"])])
        self.check_join_state_create(g, [("fork4", ['add3_buffer_read', "add2"])])

        self.assertEqual(g.instances["fork4"].join_partial_order, ["out1", "out2", "out3", "out4"])

    def test_join_bug(self):
        p = Program(
            Fork3, Add,
            ElementInstance("Fork3", "fork"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork", "add1", "out3", "in1"),
            Connect("fork", "add1", "out2", "in2"),
            Connect("fork", "add2", "out1", "in2"),
            Connect("add1", "add2", "out", "in1"),
        )

        g = generate_graph(p, False)
        roots = self.find_roots(g)
        self.assertEqual(set(["fork"]), roots)

        self.check_join_ports_same_thread(g, [("add1", ["in1", "in2"]), ("add2", ["in1", "in2"])])
        self.check_join_state_create(g, [("fork", ["add1", "add2"])])

        self.assertEqual(g.instances["fork"].join_partial_order, ['out3', 'out2', 'out1'])
