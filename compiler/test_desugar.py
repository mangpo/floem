from desugaring import desugar_spec_impl
from codegen import *
from standard_elements import *
import unittest


class TestDesugar(unittest.TestCase):

    def find_roots(self, g):
        return g.find_roots()

    def find_subgraph(self, g, root, subgraph):
        instance = g.instances[root]
        if instance.name not in subgraph:
            subgraph.add(instance.name)
            for ele,port in instance.output2ele.values():
                self.find_subgraph(g, ele, subgraph)
        return subgraph

    def test_api_para_para(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f[4]"),
            ElementInstance("Forward", "g[4]"),
            Connect("f[i]", "g[i]"),
            APIFunction("identity[4]", ["int"], "int"),
            ResourceMap("identity[i]", "f[i]"),
            ResourceMap("identity[i]", "g[i]"),
        )
        p = desugar_spec_impl(p)
        g = generate_graph(p, True, False)
        self.assertEqual(8, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f0','f1','f2','f3']), roots)
        self.assertEqual(set(['f0', 'g0']), self.find_subgraph(g, 'f0', set([])))
        self.assertEqual(set(['f1', 'g1']), self.find_subgraph(g, 'f1', set([])))
        self.assertEqual(set(['f2', 'g2']), self.find_subgraph(g, 'f2', set([])))
        self.assertEqual(set(['f3', 'g3']), self.find_subgraph(g, 'f3', set([])))

    def test_trigger(self):
        p = Program(
            Forward, Drop,
            ElementInstance("Forward", "f[4]"),
            ElementInstance("Drop", "d[4]"),
            Connect("f[i]", "d[i]"),
            APIFunction("run[4]", ["int"], None),
            ResourceMap("run[i]", "f[i]"),
            InternalTrigger("t[4]"),
            ResourceMap("t[i]", "d[i]"),
        )
        p = desugar_spec_impl(p)
        g = generate_graph(p, True, False)
        self.assertEqual(16, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f0','f1','f2','f3', 'd0_buffer_read', 'd1_buffer_read', 'd2_buffer_read', 'd3_buffer_read']), roots)

    def test_spec_impl(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f"),
            ElementInstance("Forward", "g"),
            Spec([
                APIFunction("run", ["int"], "int"),
                ResourceMap("run", "f"),
                ResourceMap("run", "g"),
                Connect("f", "g")
            ]),
            Impl([
                Connect("f", "g"),
                APIFunction("put", ["int"], None),
                ResourceMap("put", "f"),
                APIFunction("get", [], "int"),
                ResourceMap("get", "g"),
            ])
        )
        dp = desugar_spec_impl(p, "spec")
        g = generate_graph(dp, True, False)
        self.assertEqual(2, len(g.instances))
        self.assertEqual(set(['f']), self.find_roots(g))

        dp = desugar_spec_impl(p, "impl")
        g = generate_graph(dp, True, False)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(set(['f', 'g_buffer_read']), self.find_roots(g))

        dp = desugar_spec_impl(p, "compare")
        g = generate_graph(dp, True, False)
        self.assertEqual(6, len(g.instances))
        self.assertEqual(set(['_spec_f', '_impl_f', '_impl_g_buffer_read']), self.find_roots(g))

    def test_init(self):
        self.assertEqual(concretize_init("s[4]"), ['s0','s1', 's2', 's3'])

        init = concretize_init(AddressOf('s[4]'))
        expect = [AddressOf('s{0}'.format(x)) for x in range(4)]
        self.assertEqual(init, expect)

        init = concretize_init([AddressOf('s[4]')])
        expect = [[AddressOf('s{0}'.format(x)) for x in range(4)]]
        expect_str = '{{' + ','.join(['&s{0}'.format(x) for x in range(4)]) + '}}'
        self.assertEqual(init, expect)
        self.assertEqual(expect_str, get_str_init(init))

    def test_init_end2end(self):
        p = Program(
            State("One", "int x;"),
            State("Multi", "One* cores[4];"),
            StateInstance("One", "one[4]"),
            StateInstance("Multi", "all", [AddressOf("one[4]")])
        )
        dp = desugar_spec_impl(p)
        g = generate_graph(dp, False)
        all = g.state_instances["all"]
        expect = [[AddressOf("one" + str(i)) for i in range(4)]]
        self.assertEqual(expect, all.init)

    def test_init_end2end_another(self):
        p = Program(
            State("One", "int x;"),
            State("Multi", "One* core;"),
            StateInstance("One", "one[4]"),
            StateInstance("Multi", "all[4]", [AddressOf("one[4]")])
        )
        dp = desugar_spec_impl(p)
        g = generate_graph(dp, False)
        all = g.state_instances["all0"]
        self.assertEqual([AddressOf("one0")], all.init)