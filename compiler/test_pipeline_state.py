from compiler import *
from pipeline_state import find_all_fields
import unittest
import queue_smart


class TestPipelineState(unittest.TestCase):
    def check_live_all(self, g, live_list):
        visit = []
        for name, live in live_list:
            visit.append(name)
            if isinstance(live, list):
                self.assertEqual(set(live), g.instances[name].liveness, "Error at %s: expect %s, got %s."
                                 % (name, live, g.instances[name].liveness))
            else:
                self.assertEqual(live, g.instances[name].liveness, "Error at %s: expect %s, got %s."
                                 % (name, live, g.instances[name].liveness))

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

    def test_smart_queue(self):
        n_cases = 2
        queue = queue_smart.Queue("smart_queue", 10, 4, 2)
        Enq_ele = Element("smart_enq_ele",
                               [Port("in" + str(i), []) for i in range(n_cases)],
                               [Port("out", [])],"output { out(); }")
        Deq_ele = Element("smart_deq_ele",
                               [Port("in_core", ["int"]), Port("in", [])],
                               [Port("out" + str(i), []) for i in range(n_cases)],"output { out0(); out1(); }")
        Enq_ele.special = queue
        Deq_ele.special = queue
        enq = ElementInstance("smart_enq_ele", "smart_enq")
        deq = ElementInstance("smart_deq_ele", "smart_deq")
        queue.enq = enq
        queue.deq = deq
        p = Program(
            State("mystate", "int a; int a0; int b0;"),
            Element("Save",
                    [Port("in", ["int"])],
                    [Port("out", [])],
                    r'''
                    state.a = in(); output { out(); }'''),
            Element("Classify",
                    [Port("in", [])],
                    [Port("out0", []), Port("out1", [])],
                    r'''
                    output switch { case (state.a % 2) == 0: out0();
                                    else: out1(); }'''),
            Element("A0", [Port("in", [])], [Port("out", [])], r'''state.a0 = state.a + 100; output { out(); }'''),
            Element("B0", [Port("in", [])], [Port("out", [])], r'''state.b0 = state.a * 2; output { out(); }'''),
            Element("A1", [Port("in", [])], [], r'''printf("a1 %d\n", state.a0);'''),
            Element("B1", [Port("in", [])], [], r'''printf("b1 %d\n", state.b0);'''),
            Enq_ele,
            Deq_ele,
            enq,
            deq,
            ElementInstance("Save", "save"),
            ElementInstance("Classify", "classify"),
            ElementInstance("A0", "a0"),
            ElementInstance("B0", "b0"),
            ElementInstance("A1", "a1"),
            ElementInstance("B1", "b1"),
            PipelineState("save", "mystate"),
            Connect("save", "classify"),
            Connect("classify", "a0", "out0"),
            Connect("classify", "b0", "out1"),
            Connect("a0", "smart_enq", "out", "in0"),
            Connect("b0", "smart_enq", "out", "in1"),
            Connect("smart_enq", "smart_deq", "out", "in"),
            Connect("smart_deq", "a1", "out0"),
            Connect("smart_deq", "b1", "out1"),
            APIFunction("tin", ["int"], None),
            APIFunction("tout", ["int"], None),
            ResourceMap("tin", "save"),
            ResourceMap("tin", "classify"),
            ResourceMap("tin", "a0"),
            ResourceMap("tin", "b0"),
            ResourceMap("tin", "smart_enq"),
            ResourceMap("tout", "smart_deq"),
            ResourceMap("tout", "a1"),  # TODO: join node after this
            ResourceMap("tout", "b1"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("save", []),
                                ("classify", ["a"]),
                                ("a0", ["a"]), ("b0", ["a"]),
                                ("a1", ["a0"]), ("b1", ["b0"]),
                                ("smart_enq", {0: set(["a0"]), 1: set(["b0"])}),
                                ("smart_deq", None)
                                ])


    def test_smart_queue2(self):
        n_cases = 2
        queue = queue_smart.Queue("smart_queue", 10, 4, 2)
        Enq_ele = Element("smart_enq_ele",
                               [Port("in" + str(i), []) for i in range(n_cases)],
                               [Port("out", [])],"output { out(); }")
        Deq_ele = Element("smart_deq_ele",
                               [Port("in_core", ["int"]), Port("in", [])],
                               [Port("out" + str(i), []) for i in range(n_cases)],"output { out0(); out1(); }")
        Enq_ele.special = queue
        Deq_ele.special = queue
        enq = ElementInstance("smart_enq_ele", "smart_enq")
        deq = ElementInstance("smart_deq_ele", "smart_deq")
        queue.enq = enq
        queue.deq = deq
        p = Program(
            State("mystate", "int a; int a0; int b0;"),
            Element("Save",
                    [Port("in", ["int"])],
                    [Port("out", [])],
                    r'''
                    state.a = in(); output { out(); }'''),
            Element("Classify",
                    [Port("in", [])],
                    [Port("out0", []), Port("out1", [])],
                    r'''
                    output switch { case (state.a % 2) == 0: out0();
                                    else: out1(); }'''),
            Element("A0", [Port("in", [])], [Port("out", [])], r'''state.a0 = state.a + 100; output { out(); }'''),
            Element("B0", [Port("in", [])], [Port("out", [])], r'''state.b0 = state.a * 2; output { out(); }'''),
            Element("Fork", [Port("in", [])], [Port("out0", []), Port("out1", [])], r'''output { out0(); out1(); }'''),
            Element("NOP", [Port("in", [])], [Port("out", [])], r'''output { out(); }'''),
            Element("Join", [Port("in0", []), Port("in1", [])], [], r'''printf("a1 %d\n", state.a0);'''),
            Element("B1", [Port("in", [])], [], r'''printf("b1 %d\n", state.b0);'''),
            Enq_ele,
            Deq_ele,
            enq,
            deq,
            ElementInstance("Save", "save"),
            ElementInstance("Classify", "classify"),
            ElementInstance("A0", "a0"),
            ElementInstance("B0", "b0"),
            ElementInstance("Fork", "fork"),
            ElementInstance("NOP", "nop0"),
            ElementInstance("NOP", "nop1"),
            ElementInstance("Join", "join"),
            #ElementInstance("A1", "a1"),
            ElementInstance("B1", "b1"),
            PipelineState("save", "mystate"),
            Connect("save", "classify"),
            Connect("classify", "a0", "out0"),
            Connect("classify", "b0", "out1"),
            Connect("a0", "smart_enq", "out", "in0"),
            Connect("b0", "smart_enq", "out", "in1"),
            Connect("smart_enq", "smart_deq", "out", "in"),
            #Connect("smart_deq", "a1", "out0"),
            Connect("smart_deq", "fork", "out0"),
            Connect("fork", "nop0", "out0"),
            Connect("fork", "nop1", "out1"),
            Connect("nop0", "join", "out", "in0"),
            Connect("nop1", "join", "out", "in1"),
            Connect("smart_deq", "b1", "out1"),
            APIFunction("tin", ["int"], None),
            APIFunction("tout", ["int"], None),
            ResourceMap("tin", "save"),
            ResourceMap("tin", "classify"),
            ResourceMap("tin", "a0"),
            ResourceMap("tin", "b0"),
            ResourceMap("tin", "smart_enq"),
            ResourceMap("tout", "smart_deq"),
            #ResourceMap("tout", "a1"),
            ResourceMap("tout", "fork"),
            ResourceMap("tout", "nop0"),
            ResourceMap("tout", "nop1"),
            ResourceMap("tout", "join"),
            ResourceMap("tout", "b1"),
        )

        gen = program_to_graph_pass(p)
        pipeline_state_pass(gen, check=False)
        g = gen.graph

        self.check_live_all(g, [("save", []),
                                ("classify", ["a"]),
                                ("a0", ["a"]), ("b0", ["a"]),
                                ("fork", ["a0"]),
                                ("nop0", []),
                                ("nop1", []),
                                ("join", ["a0"]),
                                ("b1", ["b0"]),
                                ("smart_enq", {0: set(["a0"]), 1: set(["b0"])}),
                                ("smart_deq", None)
                                ])
