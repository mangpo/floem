from compiler import *
from pipeline_state import find_all_fields
import unittest


class TestPipelineState(unittest.TestCase):
    def check_live_all(self, g, live_list):
        visit = []
        for name, live in live_list:
            visit.append(name)
            self.assertEqual(set(live), g.instances[name].liveness)

        for name in g.instances:
            if name not in visit:
                self.assertEqual(set(), g.instances[name].liveness)

    def test_fields_extraction(self):
        src, fields, code = find_all_fields("pkt->mcr.request.opcode;")
        self.assertEqual(src, "pkt->mcr.request.opcode")
        self.assertEqual(fields, ['pkt', 'mcr', 'request', 'opcode'])
        self.assertEqual(code, ';')

        src, fields, code = find_all_fields("m->payload + m->mcr.request.extlen;")
        self.assertEqual(src, "m->payload")
        self.assertEqual(fields, ['m', 'payload'])
        self.assertEqual(code, ' + m->mcr.request.extlen;')

    def test_simple_fail(self):
        p = Program(
            Element("E1",
                    [Port("in", ["int"])],
                    [Port("out", [])],
                    r'''state.a = in() output { out(); }'''),
            Element("E2",
                    [Port("in", [])],
                    [],
                    r'''printf("%d %d\n", state.a, state.b);'''),
            ElementInstance("E1", "e1"),
            ElementInstance("E2", "e2"),
            Connect("e1", "e2"),
            State("mystate", "int a; int b;"),
            PipelineState("e1", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("e1", ["b"]), ("e2", ["a", "b"])])


    def test_simple_pass(self):
        p = Program(
            Element("E0",
                    [Port("in", ["int", "int"])],
                    [Port("out", ["int"])],
                    r'''
                    (int a, int b) = in();
                    state.a = a; output { out(b); }'''),
            Element("E1",
                    [Port("in", ["int"])],
                    [Port("out", [])],
                    r'''state.b = in() output { out(); }'''),
            Element("E2",
                    [Port("in", [])],
                    [],
                    r'''printf("%d %d\n", state.a, state.b);'''),
            ElementInstance("E0", "e0"),
            ElementInstance("E1", "e1"),
            ElementInstance("E2", "e2"),
            Connect("e0", "e1"),
            Connect("e1", "e2"),
            State("mystate", "int a; int b;"),
            PipelineState("e0", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("e1", ["a"]), ("e2", ["a", "b"])])


    def test_still_live(self):
        p = Program(
            Element("MyFork",
                    [Port("in", [])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    output { out1(); out2() }'''),
            Element("Def",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.a = 99; output { out(); }'''),
            Element("Join",
                    [Port("in1", []), Port("in2", [])],
                    [],
                    r'''printf("%d\n", state.a);'''),
            Element("Use",
                    [Port("in", [])],
                    [],
                    r'''printf("%d\n", state.a);'''),
            ElementInstance("MyFork", "fork1"),
            ElementInstance("MyFork", "fork2"),
            ElementInstance("Def", "def"),
            ElementInstance("Use", "use"),
            ElementInstance("Join", "join"),
            Connect("fork1", "def", "out1"),
            Connect("fork1", "fork2", "out2"),
            Connect("def", "join", "out", "in1"),
            Connect("fork2", "join", "out1", "in2"),
            Connect("fork2", "use", "out2"),
            State("mystate", "int a;"),
            PipelineState("fork1", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("fork1", ["a"]), ("fork2", ["a"]), ("join", ["a"]), ("use", ["a"]), ("def", [])])
