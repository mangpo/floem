from compiler import *
from pipeline_state import find_all_fields
import unittest


class TestPipelineState(unittest.TestCase):
    def check_live_all(self, g, live_list):
        visit = []
        for name, live in live_list:
            visit.append(name)
            self.assertEqual(set(live), g.instances[name].liveness, "Error at %s: expect %s" % (name, live))

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

    def test_either(self):
        p = Program(
            Element("Choice",
                    [Port("in", ["int"])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    int c = in();
                    output switch { case c: out1(); else: out2(); }'''),
            Element("Def",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.a = 99; output { out(); }'''),
            Element("Nop",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''output { out(); }'''),
            Element("Use",
                    [Port("in", [])],
                    [],
                    r'''printf("%d\n", state.a);'''),
            ElementInstance("Choice", "choice"),
            ElementInstance("Def", "def"),
            ElementInstance("Use", "use"),
            ElementInstance("Nop", "nop1"),
            ElementInstance("Nop", "nop2"),
            Connect("choice", "def", "out1"),
            Connect("choice", "nop1", "out2"),
            Connect("def", "nop2"),
            Connect("nop1", "nop2"),
            Connect("nop2", "use"),
            State("mystate", "int a;"),
            PipelineState("choice", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("choice", ["a"]), ("nop1", ["a"]), ("nop2", ["a"]), ("use", ["a"]), ("def", [])])

    def test_both(self):
        p = Program(
            Element("MyFork",
                    [Port("in", [])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    output  { out1(); out2(); }'''),
            Element("DefA",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.a = 99; output { out(); }'''),
            Element("DefB",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''state.b = 99; output { out(); }'''),
            Element("Join",
                    [Port("in1", []), Port("in2", [])],
                    [Port("out", [])],
                    r'''output { out(); }'''),
            Element("Use",
                    [Port("in", [])],
                    [],
                    r'''printf("%d\n", state.a + state.b);'''),
            ElementInstance("MyFork", "fork"),
            ElementInstance("DefA", "defA"),
            ElementInstance("DefB", "defB"),
            ElementInstance("Use", "use"),
            ElementInstance("Join", "join"),
            Connect("fork", "defA", "out1"),
            Connect("fork", "defB", "out2"),
            Connect("defA", "join", "out", "in1"),
            Connect("defB", "join", "out", "in2"),
            Connect("join", "use"),
            State("mystate", "int a; int b;"),
            PipelineState("fork", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("fork", []), ("defA", []), ("defB", []), ("join", ["a", "b"]), ("use", ["a", "b"])])

    def test_complicated(self):
        p = Program(
            Element("Choice",
                    [Port("in", ["int"])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    int c = in();
                    output switch { case c: out1(); else: out2(); }'''),
            Element("ForkB1",
                    [Port("in", [])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    state.b = 99;
                    output  { out1(); out2(); }'''),
            Element("ForkB2",
                    [Port("in", [])],
                    [Port("out1", []), Port("out2", [])],
                    r'''
                    output  { out1(); out2(); }'''),
            Element("C1",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''
                    state.a = 99;
                    output { out(); }'''),
            Element("C2",
                    [Port("in", [])],
                    [Port("out", [])],
                    r'''
                    output { out(); }'''),
            Element("JoinUse",
                    [Port("in1", []), Port("in2", [])],
                    [],
                    r'''
                    printf("%d\n", state.a + state.b);'''),
            ElementInstance("Choice", "a"),
            ElementInstance("ForkB1", "b1"),
            ElementInstance("ForkB2", "b2"),
            ElementInstance("C1", "c1"),
            ElementInstance("C2", "c2"),
            ElementInstance("JoinUse", "use"),
            Connect("a", "b1", "out1"),
            Connect("a", "b2", "out2"),
            Connect("b1", "c1", "out1"),
            Connect("b1", "c2", "out2"),
            Connect("b2", "c1", "out1"),
            Connect("b2", "c2", "out2"),
            Connect("c1", "use", "out", "in1"),
            Connect("c2", "use", "out", "in2"),
            State("mystate", "int a; int b;"),
            PipelineState("a", "mystate"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("a", ["b"]),
                                ("b1", []), ("b2", ["b"]),
                                ("c1", []), ("c2", []), # passing nodes
                                ("use", ["a", "b"])])

