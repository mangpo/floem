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

        self.check_join_ports_same_thread(g2, [])
        self.check_join_state_create(g2, [])
        self.check_join_call(g2, [])

    def test_fork_join(self):
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
            Connect("Sub", "Print", "out", "in2"),
            InternalTrigger("Print")
        )

        g = generate_graph(p, False)
        self.assertEqual(4, len(g.instances))

        g = generate_graph(p, True)
        self.assertEqual(7, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['Fork', '_buffer_Print_read']), roots)
        self.assertEqual(set(['Fork', 'Add', '_buffer_Print_in1_write', 'Sub', '_buffer_Print_in2_write']),
                         self.find_subgraph(g, 'Fork', set()))
        self.assertEqual(set(['_buffer_Print_read', 'Print']),
                         self.find_subgraph(g, '_buffer_Print_read', set()))

        self.check_join_ports_same_thread(g, [])
        self.check_join_state_create(g, [])
        self.check_join_call(g, [])

    def test_fork_join_thread2(self):
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
            Connect("Sub", "Print", "out", "in2"),
            InternalTrigger("Sub")
        )

        g = generate_graph(p, False)
        self.assertEqual(4, len(g.instances))

        g = generate_graph(p, True)
        self.assertEqual(8, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['Fork', '_buffer_Sub_read']), roots)
        self.assertEqual(5, len(self.find_subgraph(g, 'Fork', set())))
        self.assertEqual(3, len(self.find_subgraph(g, '_buffer_Sub_read', set())))

        self.check_join_ports_same_thread(g, [])
        self.check_join_state_create(g, [])
        self.check_join_call(g, [])

    def test_fork_join_half(self):
        p = Program(
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Print",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [],
                    r'''printf("%d %d\n",in1(), in2());'''),
            ElementInstance("Forwarder", "f1"),
            ElementInstance("Forwarder", "f2"),
            ElementInstance("Print", "Print"),
            Connect("f1", "Print", "out", "in1"),
            Connect("f2", "Print", "out", "in2"),
            ExternalTrigger("f2")
        )

        try:
            g = generate_graph(p, False)
        except Exception as e:
            self.assertNotEqual(e.message.find("There is no dominant element instance"), -1)
        else:
            self.fail('Exception is not raised.')

        g = generate_graph(p, True)
        self.assertEqual(5, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(["f1", "f2"]), roots)
        self.assertEqual(set(["f1", '_buffer_Print_read', "Print"]), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(["f2", '_buffer_Print_in2_write']), self.find_subgraph(g, 'f2', set()))
        self.check_join_ports_same_thread(g, [])

    def test_join_only(self):
        p = Program(
            Element("Print",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [],
                    r'''printf("%d %d\n",in1(), in2());'''),
            ElementInstance("Print", "Print")
        )

        try:
            g = generate_graph(p, True)
        except Exception as e:
            self.assertNotEqual(e.message.find("is not connected to any instance"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_multi_joins(self):
        p = Program(
            Element("Fork2",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x);'''),
            Element("Fork3",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"]), Port("out3", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x); out3(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Add",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in1() + in2());'''),
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

        self.check_join_call(g, [("fork2", ["add1"]), ("f2", ["add2"])])

    def test_nested_joins(self):
        p = Program(
            Element("Fork2",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''(int x) = in(); out1(x); out2(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Element("Add",
                    [Port("in1", ["int"]), Port("in2", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in1() + in2());'''),
            ElementInstance("Fork2", "fork1"),
            ElementInstance("Fork2", "fork2"),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            ElementInstance("Forward", "f3"),
            ElementInstance("Add", "add1"),
            ElementInstance("Add", "add2"),
            Connect("fork1", "fork2", "out1"),
            Connect("fork1", "f3", "out2"),
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
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            Composite("Unit", [Port("in", ("f1", "in"))], [Port("out", ("f2", "out"))], [], [],
                      Program(
                          ElementInstance("Forwarder", "f1"),
                          ElementInstance("Forwarder", "f2"),
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
        self.check_join_ports_same_thread(g, [])

    def test_nonconflict_input(self):
        p = Program(
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Forwarder", "f1"),
            ElementInstance("Forwarder", "f2"),
            ElementInstance("Forwarder", "f3"),
            Connect("f1", "f3"),
            Connect("f2", "f3"),
        )
        g = generate_graph(p)
        self.assertEqual(3, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f1', 'f2']), roots)
        self.assertEqual(set(['f1', 'f3']), self.find_subgraph(g, 'f1', set()))
        self.assertEqual(set(['f2', 'f3']), self.find_subgraph(g, 'f2', set()))
        self.check_join_ports_same_thread(g, [])

    def test_nonconflict_input_thread(self):
        p = Program(
            Element("Forwarder",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Forwarder", "f1"),
            ElementInstance("Forwarder", "f2"),
            ElementInstance("Forwarder", "f3"),
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
        self.check_join_ports_same_thread(g, [])

    def test_error_both_internal_external(self):
        p = Program(
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
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
                    r'''out(in() + 1);'''),
            Element("Print",
                    [Port("in", ["int"])],
                    [],
                    r'''printf("%d\n", in());'''),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Print", "print"),
            Connect("inc1", "print"),
            APIFunction("add_and_print", "inc1", "in", "print", None)
        )
        g = generate_graph(p)
        self.assertEqual(2, len(g.instances))
        self.assertEqual(0, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['inc1']), roots)
        self.check_api_return(g, [])
        self.check_api_return(g, [])
        self.check_api_return_final(g, [])

    def test_API_basic_output(self):
        p = Program(
            Element("Inc",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in() + 1);'''),
            ElementInstance("Inc", "inc1"),
            ElementInstance("Inc", "inc2"),
            Connect("inc1", "inc2"),
            APIFunction("add2", "inc1", "in", "inc2", "out", "Add2Return")
        )
        g = generate_graph(p)
        self.assertEqual(2, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['inc1']), roots)
        self.assertEqual(set(['inc1', 'inc2']), self.find_subgraph(g, 'inc1', set()))
        self.check_api_return(g, [("inc1", "Add2Return"), ("inc2", "Add2Return")])
        self.check_api_return_from(g, [("inc1", "inc2")])
        self.check_api_return_final(g, ["inc2"])

    def test_API_blocking_read(self):
        p = Program(
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("read", "f2", None, "f2", "out", "int")
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
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            APIFunction("func", "f1", "in", "f1", None)
        )
        try:
            g = generate_graph(p)
        except Exception as e:
            print e.message
            self.assertNotEqual(e.message.find("return element instance 'f1' has a continuing element instance"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_API_no_return_okay(self):
        p = Program(
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Forward", "f1"),
            ElementInstance("Forward", "f2"),
            Connect("f1", "f2"),
            InternalTrigger("f2"),
            APIFunction("func", "f1", "in", "f1", None)
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
            Element("Dup",
                    [Port("in", ["int"])],
                    [Port("out1", ["int"]), Port("out2", ["int"])],
                    r'''int x = in(); out1(x); out2(x);'''),
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
            ElementInstance("Dup", "dup"),
            ElementInstance("Forward", "fwd"),
            Connect("dup", "fwd", "out1"),
            InternalTrigger("fwd"),
            APIFunction("func", "dup", "in", "dup", "out2", "int")
        )
        g = generate_graph(p)
        generate_code(g)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(1, len(g.states))
        roots = self.find_roots(g)
        self.assertEqual(set(['dup', '_buffer_fwd_read']), roots)
        self.assertEqual(2, len(self.find_subgraph(g, 'dup', set())))
        self.assertEqual(2, len(self.find_subgraph(g, '_buffer_fwd_read', set())))

        self.check_api_return(g, [("dup", "int")])
        self.check_api_return_from(g, [])
        self.check_api_return_final(g, ["dup"])

    def test_composite_scope(self):
        p = Program(
            Element("Forward",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''out(in());'''),
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