import os
import unittest
from elements_library import *


class TestDSL(unittest.TestCase):

    def find_subgraph(self, g, root, subgraph):
        instance = g.instances[root]
        if instance.name not in subgraph:
            subgraph.add(instance.name)
            for ele,port in instance.output2ele.values():
                self.find_subgraph(g, ele, subgraph)
        return subgraph

    def test_run(self):
        tests = ["hello.py",
                 "join_inject.py",
                 "join_inject_forkjoin.py",
                 "state_local.py",
                 "state_shared.py",
                 "composite_thread_port.py",
                 "composite_scope.py",
                 "API_increment1.py",
                 "API_increment2.py",
                 "API_increment3.py",
                 "API_read_blocking1.py",
                 "API_read_blocking2.py",
                 "API_and_trigger.py",
                 "API_return.py",
                 "spec_impl.py",
                 "spec_impl_at.py",
                 "probe_spec_impl.py",
                 "probe_multi.py",
                 "inject_queue.py",
                 "circular_queue.py",
                 "circular_queue2.py",
                 "circular_queue_multicore.py",
                 "circular_queue_multicore2.py",
                 "circular_queue_multicore3.py",
                 "circular_queue_multicore4.py",
                 "copy_queue1.py",
                 "copy_queue2.py",
                 "composite_at1.py",
                 "composite_at2.py",
                 "composite_at3.py",
                 "order_empty_port.py",
                 "order_join.py",
                 "syscall.py",
                 "extract_field.py",
                 "nested_spec_impl_in_compo.py",
                 "nested_compo_in_impl.py",
                 "API_insert_start_element.py",
                 "multiprocesses.py",
                 "multiprocesses_shm.py",
                 "forkjoin.py",
                 "double_connection.py",  # TODO: Is this the semantics we want?
                 "classify_return2.py",
                 ]

        tests2 = ["join.py",
                  "join_multiple.py",
                  "classify_join1.py",
                  "double_connect.py",
                  "buffer.py",
                  "state_nested_composite.py",
                  "probe_composite.py",
                  "probe_spec_impl.py",
                  "table.py",
                  "composite.py",
                  "variable_length_field.py",
                  "choice_join.py",
                  "memory_region.py",
                  #"extract_field_spec_impl.py",
                  ]

        tests3 = ["simple.py",
                  "multiple_queues.py",
                  "queue_shared_pointer.py",
                  "queue_shared_data.py",
                  "auto_inserted_queue.py",
                  "smart_queue_entry.py",
                  "smart_queue_entry2.py",
                  "smart_queue_many2one.py",]

        for test in tests:
            status = os.system("cd programs; python " + test + "; cd ..")
            self.assertEqual(status, 0, "Error at " + test)
        for test in tests2:
            status = os.system("cd programs_testing; python " + test + "; cd ..")
            self.assertEqual(status, 0, "Error at " + test)
        for test in tests3:
            status = os.system("cd abstracts; python " + test + "; cd ..")
            self.assertEqual(status, 0, "Error at " + test)

    def test_conflict_input(self):
        reset()
        Forward = create_identity("Forward", "int")
        Add = create_add("Add", "int")
        f1 = Forward("f1")
        f2 = Forward("f2")
        add = Add("add")
        add(f1(None), None)
        add(f2(None), None)

        t = internal_thread("t")
        t.run(f1, f2, add)

        c = Compiler()
        c.remove_unused = False
        try:
            c.generate_code()
        except Exception as e:
            self.assertNotEqual(
                e.message.find("Resource 't' has more than one starting element instance."), -1)
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

        x1 = c1(None, t1.run, t2.run)
        x2 = c2(x1, t2.run, t3.run)

        c = Compiler()
        g = c.generate_graph()
        self.assertEqual(8, len(g.instances))
        roots = g.find_roots()
        self.assertEqual(set(['c1_f1', 'c1_f2_buffer_read', 'c2_f2_buffer_read']), roots)

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
        c.remove_unused = False
        g = c.generate_graph()
        self.assertEqual(4, len(g.instances))
        roots = g.find_roots()
        self.assertEqual(set(['c1_inc1']), roots)
        self.assertEqual(set(['count', 'c1_count', 'c2_count']), set(g.state_instances.keys()))

    def test_api_exception(self):
        reset()
        try:
            Forward = create_identity("Forward", "int")

            @API("func")
            def func(x):
                def spec(x):
                    f = Forward()
                    return f(x)

                def impl(x):
                    f1 = Forward()
                    f2 = Forward()
                    return f2(f1(x))

                compo = create_spec_impl("compo", spec, impl)
                return compo(x)
        except Exception as e:
            self.assertNotEqual(e.message.find("cannot wrap around spec and impl"), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_api_okay(self):
        reset()
        Forward = create_identity("Forward", "int")
        Inc = create_add1("Inc", "int")
        def spec(x):
            @API("func")
            def func(x):
                f = Forward()
                return f(x)
            return func(x)

        def impl(x):
            @API("func")
            def func(x):
                f1 = Inc()
                f2 = Inc()
                return f2(f1(x))
            return func(x)

        compo = create_spec_impl("compo", spec, impl)

        c = Compiler()
        c.desugar_mode = "spec"
        c.testing = "out(func(123));"
        c.generate_code_and_run([123])


        c.desugar_mode = "impl"
        c.testing = "out(func(123));"
        c.generate_code_and_run([125])

    def test_insert_fork(self):
        reset()
        Inc = create_add1("Inc", "int")

        inc1 = Inc()
        inc2 = Inc()
        inc3 = Inc()

        x1 = inc1()
        x2 = inc2(x1)
        x3 = inc3(x1)

        c = Compiler()
        c.remove_unused = False
        g = c.generate_graph()
        self.assertEqual(4, len(g.instances))  # fork is added.

    def test_insert_fork_spec_impl(self):
        reset()
        Inc = create_add1("Inc", "int")
        Drop = create_drop("Drop", "int")

        inc1 = Inc("inc1")

        def spec(x1):
            inc2 = Inc("inc2")
            return inc2(x1)

        def impl(x1):
            inc2 = Inc("inc2")
            inc3 = Inc("inc3")
            drop = Drop("drop")
            x2 = inc2(x1)
            x3 = inc3(x1)
            drop(x3)
            return x2

        compo = create_spec_impl("compo", spec, impl)
        compo(inc1(None))

        t = API_thread("f", ["int"], "int")
        t.run(inc1, compo)

        c = Compiler()
        c.remove_unused = False
        c.resource = False
        c.desugar_mode = "compare"
        g = c.generate_graph()
        roots = g.find_roots()
        self.assertEqual(roots, set(['_spec_inc1', '_impl_inc1']))
        self.assertEqual(self.find_subgraph(g, '_impl_inc1', set()),
                         set(['_impl_inc1', '_impl_inc1_out_fork1_inst', '_impl_compo_inc2', '_impl_compo_inc3', '_impl_compo_drop']))

    def test_compo_nop(self):
        reset()
        try:
            Forward = create_identity("Forward", "int")
            f1 = Forward()
            f2 = Forward()
            @composite_instance("compo")
            def compo(x):
                return x  # TODO: should throw exception

            f2(compo(f1(None)))

        except Exception as e:
            self.assertNotEqual(e.message.find("Composite 'compo' should not connect an input to an output directly."), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_illegal_order(self):
        reset()
        Forward = create_identity("Forward", "int")
        f1 = Forward()
        f2 = Forward()
        f3 = Forward()

        f3(f2(f1(None)))
        t = API_thread("run", ["int"], "int")
        t.run(f1, f2, f3)
        t.run_order(f3, f2)

        try:
            c = Compiler()
            c.generate_graph()
        except Exception as e:
            self.assertNotEqual(e.message.find("Cannot order 'Forward2' before 'Forward1' because 'Forward1' points to 'Forward2'."), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_api_multi_return(self):
        reset()
        Fork = create_fork("Fork", 2, "int")
        Forward = create_identity("Forward", "int")

        fork = Fork()
        f1 = Forward()
        f2 = Forward()
        f3 = Forward()

        x1, x2 = fork(None)
        f3(f1(x1))
        f3(f2(x2))

        t = API_thread("run", ["int"], "int")
        t.run(fork, f1, f2, f3)

        try:
            c = Compiler()
            c.generate_graph()
        except Exception as e:
            self.assertNotEqual(e.message.find("the return instance 'Forward3' more than once"), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_api_default_val(self):
        reset()
        Choice = create_element("Choice", [Port("in", ["int"])], [Port("out1", ["int"]), Port("out2", ["int"])],
                                r'''
                                int x = in();
                                output switch { case (x > 0): out1(x); else: out2(x); }
                                ''')
        Forward = create_identity("Forward", "int")
        Drop = create_drop("Drop", "int")

        choice = Choice()
        f1 = Forward()
        f2 = Forward()
        drop = Drop()

        x1, x2 = choice()
        drop(x2)
        f2(f1(x1))

        t = API_thread("run", ["int"], "int", default_val=-1)
        t.run(choice, f1, f2, drop)

        c = Compiler()
        c.testing = "out(run(3)); out(run(-3)); out(run(0));"
        c.generate_code_and_run([3, -1, -1])

    def test_api_either(self):
        reset()
        Choice = create_element("Choice", [Port("in", ["int"])], [Port("out1", ["int"]), Port("out2", ["int"])],
                                r'''
                                int x = in();
                                output switch { case (x % 2 == 0): out1(x); else: out2(x); }
                                ''')
        Forward = create_identity("Forward", "int")
        Inc = create_add1("Inc", "int")

        choice = Choice()
        nop = Forward()
        inc = Inc()
        end = Forward()

        even, odd = choice(None)
        end(nop(even))
        end(inc(odd))

        t = API_thread("run", ["int"], "int")
        t.run(choice, inc, nop, end)

        c = Compiler()
        c.testing = "out(run(3)); out(run(4)); out(run(5));"
        c.generate_code_and_run([4, 4, 6])

    def test_api_join(self):
        reset()
        Fork = create_fork("Fork", 2, "int")
        Add = create_add("Add", "int")

        @API("run")
        def run(x):
            fork1 = Fork("fork1")
            fork2 = Fork("fork2")
            add1 = Add("add1")
            add2 = Add("add2")

            x1, x2 = fork1(x)
            x3, x4 = fork2(x2)
            x5 = add1(x1, x3)
            y = add2(x5, x4)
            return y

        c = Compiler()
        c.testing = "out(run(1)); out(run(10));"
        c.generate_code_and_run([3, 30])

    def test_api_nested_join(self):
        reset()
        Fork2 = create_fork("Fork2", 2, "int")
        Fork3 = create_fork("Fork3", 3, "int")
        Add2 = create_add("Add2", "int")
        Add3 = create_element("Add3",
                          [Port("in1", ["int"]), Port("in2", ["int"]), Port("in3", ["int"])],
                          [Port("out", ["int"])],
                          r'''int x = in1() + in2() + in3(); output { out(x); }''')
        Forward = create_identity("Forward", "int")


        @API("run")
        def run(x):
            fork2 = Fork2("fork2")
            fork3 = Fork3("fork3")
            f1 = Forward("f1")
            f2 = Forward("f2")
            f3 = Forward("f3")
            add2 = Add2("add2")
            add3 = Add3("add3")

            fork2_o1, fork2_o2 = fork2(x)
            f1_o = f1(fork2_o1)
            fork3_o1, fork3_o2, fork3_o3 = fork3(fork2_o2)
            f2_o = f2(fork3_o2)
            f3_o = f3(fork3_o3)
            add2_o = add2(f2_o, f3_o)
            y = add3(f1_o, add2_o, fork3_o1)
            return y

        c = Compiler()
        c.testing = "out(run(1)); out(run(10));"
        c.generate_code_and_run([4, 40])

    def test_api_zero_or_one_join(self):
        reset()
        Fork = create_fork("Fork", 2, "int")
        Filter = create_element("Filter",
                          [Port("in", ["int"])],
                          [Port("out", ["int"])],
                          r'''int x = in(); output switch { case (x > 0): out(x); }''')
        Forward = create_identity("Forward", "int")
        Add = create_add("Add", "int")

        @API("run", -1)
        def run(x):
            fork = Fork()
            filter = Filter()
            f1 = Forward()
            f2 = Forward()
            add = Add()

            x1, x2 = fork(filter((x)))
            y = add(f1(x1), f2(x2))
            return y

        c = Compiler()
        c.testing = "out(run(1)); out(run(10)); out(run(-10));"
        c.generate_code_and_run([2, 20, -1])

    def test_starting_element(self):
        reset()
        Gen = create_element("Gen", [], [Port("out", ["int"])],
                             "output { out(1); }")
        Forward = create_identity("Forward", "int")
        Drop = create_drop("Drop", "int")

        gen = Gen()
        f = Forward()
        drop = Drop()
        drop(f(gen()))

        t = internal_thread("t")
        t.run(f, gen, drop)

        c = Compiler()
        c.triggers = True
        c.testing = "run_threads(); usleep(1000); kill_threads();"
        c.generate_code_and_run()

    def test_disconnection(self):
        reset()
        Gen = create_element("Gen", [], [Port("out", ["int"])],
                             "output { out(1); }")
        Forward = create_identity("Forward", "int")
        Drop = create_drop("Drop", "int")

        gen = Gen()
        f = Forward()
        drop = Drop()
        drop(f(gen()))

        gen2 = Gen()
        f2 = Forward()
        drop2 = Drop()
        drop2(f2(gen2()))

        t = internal_thread("t")
        t.run(gen, f, drop, gen2, f2, drop2)

        try:
            c = Compiler()
            c.triggers = True
            c.testing = "run_threads(); usleep(1000); kill_threads();"
            c.generate_code_and_run()
        except Exception as e:
            self.assertNotEqual(e.message.find("Resource 't' has more than one starting element instance."),
                                -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_classify_join2(self):
        reset()
        fork = create_fork_instance("fork2", 2, "int")

        Chioce = create_element("Choice",
                                [Port("in", ["int"])],
                                [Port("out1", ["int"]), Port("out2", ["int"])],
                                r'''(int x) = in(); output switch { case (x % 2 == 0): out1(x); else: out2(x); }''')
        choice1 = Chioce("choice1")
        choice2 = Chioce("choice2")

        Inc = create_add1("Inc", "int")
        inc1 = Inc("inc1")
        inc2 = Inc("inc2")

        Add = create_add("Add", "int")
        add1 = Add("add1")
        add2 = Add("add2")

        x1, x2 = fork(None)
        y1, y2 = choice1(x1)
        z1, z2 = choice2(x2)
        add1(y1, z2)
        add2(inc1(y2), inc2(z1))

        try:
            c = Compiler()
            c.resource = False
            c.remove_unused = False
            c.generate_code_and_run()
        except Exception as e:
            self.assertNotEqual(e.message.find("All its output ports must fire the same input ports of the join instance 'add2'."), -1, 'Expect undefined exception.')
        else:
            self.fail('Exception is not raised.')

    def test_auto_queue_error(self):
        reset()
        state = create_state("mystate", "int a;")
        gen = create_element_instance("gen", [Port("in", ["int"])], [Port("out", [])],
                                      "state.a = in(); output { out(); }")
        display = create_element_instance("display", [Port("in", [])], [], r'''printf("%d\n", state.a);''')

        display(gen(None))
        pipeline_state(gen, "mystate")

        t1 = API_thread("put", ["int"], None)
        t2 = API_thread("get", [], None)
        t1.run(gen)
        t2.run(display)

        CPU_process("p1", t1)
        CPU_process("p2", t2)
        master_process("p1")

        try:
            c = Compiler()
            c.generate_code_and_run([42, 123])
        except Exception as e:
            self.assertNotEqual(e.message.find("Consider inserting a smart queue between the sender instance and the receiver instance 'display'."), -1)
        else:
            self.fail('Exception is not raised.')

    def test_classify_return_error(self):
        reset()
        classify = create_element_instance("choose", [Port("in", ["int"])],
                                           [Port("out1", ["int"]), Port("out2", ["int"])],
                                           r'''
            (int x) = in();
            output switch {
                case x < 0: out1(x);
                else: out2(x);
            }
                                           ''')
        Forward = create_identity("Forward", "int")
        f1 = Forward()
        f2 = Forward()

        x1, x2 = classify(None)
        f1(x1)
        f2(x2)

        t = API_thread("run", ["int"], "int")
        t.run(classify, f1, f2)

        try:
            c = Compiler()
            c.testing = "out(run(3));"
            c.generate_code_and_run()
        except Exception as e:
            self.assertNotEqual(e.message.find("An API has too many return instances"), -1)
        else:
            self.fail('Exception is not raised.')


if __name__ == '__main__':
    unittest.main()