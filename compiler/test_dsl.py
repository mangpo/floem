import os
import unittest
from elements_library import *


class TestDSL(unittest.TestCase):

    def test_run(self):
        tests = ["hello.py",
                 "join.py",
                 "join_multiple.py",
                 "join_inject.py",
                 "buffer.py",
                 "state_local.py",
                 "state_shared.py",
                 "state_nested_composite.py",
                 "composite.py",
                 "composite_thread_port.py",
                 "composite_scope.py",
                 "API_increment.py",
                 "API_read_blocking.py",
                 "spec_impl.py",
                 "probe_composite.py",
                 "probe_multi.py",
                 "probe_spec_impl.py",
                 "inject_queue.py",
                 "circular_queue.py",
                 "circular_queue_multicore.py",
                 "table.py",
                 "composite_at1.py",
                 "composite_at2.py",
                 "composite_at3.py",
                 ]

        for test in tests:
            status = os.system("python programs_in_dsl/" + test)
            self.assertEqual(status, 0, "Error at " + test)

    def test_conflict_output(self):
        reset()
        Forward = create_identity("Forward", "int")
        f1 = Forward("f1")
        f2 = Forward()
        f3 = Forward()
        x1 = f1(None)
        f2(x1)
        f3(x1)

        c = Compiler()
        try:
            c.generate_code()
        except Exception as e:
            self.assertNotEqual(e.message.find("The output port 'out' of element instance 'f1' cannot be connected to both"), -1)
        else:
            self.fail('Exception is not raised.')

    def test_conflict_input(self):
        reset()
        Forward = create_identity("Forward", "int")
        Add = create_add("Add", "int")
        f1 = Forward("f1")
        f2 = Forward("f2")
        add = Add("add")
        add(f1(None), None)
        add(f2(None), None)

        c = Compiler()
        try:
            c.generate_code()
        except Exception as e:
            print e.message
            self.assertNotEqual(
                e.message.find("Input port 'in1' of join element instance 'add' is connected to more than one port."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_composite_with_thread(self):
        reset()
        Forward = create_identity("Forward", "int")
        def compo(x, t1, t2):
            f1 = Forward("f1")
            f2 = Forward("f2")

            y = f2(f1(x))
            t1(f1)
            t2(f2)
            return y

        Compo = create_composite("Compo", compo)
        c1 = Compo("c1")
        c2 = Compo("c2")

        t1 = API_thread("put", ["int"], None)
        t2 = internal_thread("worker")
        t3 = API_thread("get", [], "int")

        x1 = c1(None, t1.run_start, t2.run_start)
        x2 = c2(x1, t2.run, t3.run_start)

        c = Compiler()
        g = c.generate_graph()
        self.assertEqual(8, len(g.instances))
        roots = g.find_roots()
        self.assertEqual(set(['c1_f1', '_buffer_c1_f2_read', '_buffer_c2_f2_read']), roots)

    def test_composite(self):
        reset()
        Count = create_state("Count", "int count;", [0])
        Inc = create_element("Inc",
                    [Port("in", ["int"])],
                    [Port("out", ["int"])],
                    r'''local.count++; global.count++; int x = in(); output { out(x); }''',
                    None,
                    [("Count", "local"), ("Count", "global")])

        global_count = Count("count")
        def compo(x):
            count = Count("count")
            inc1 = Inc("inc1", [count, global_count])
            inc2 = Inc("inc2", [count, global_count])
            return inc2(inc1(x))

        Compo = create_composite("Compo", compo)
        c1 = Compo("c1")
        c2 = Compo("c2")
        c2(c1(None))

        c = Compiler()
        g = c.generate_graph()
        self.assertEqual(4, len(g.instances))
        roots = g.find_roots()
        self.assertEqual(set(['c1_inc1']), roots)
        self.assertEqual(set(['count', 'c1_count', 'c2_count']), set(g.state_instances.keys()))


if __name__ == '__main__':
    unittest.main()