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

        try:
            gen = program_to_graph_pass(p)
            g = pipeline_state_pass(gen)
        except AssertionError as e:
            self.assertNotEqual(e.message.find("Fields set(['b']) of a pipeline state should not be live at the beginning."), -1)
        else:
            self.fail('Exception is not raised.')


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
        pipeline_state_pass(gen)
        g = gen.graph

        self.check_live_all(g, [("e1", ["a"]), ("e2", ["a", "b"])])
