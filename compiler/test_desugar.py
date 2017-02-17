from desugaring import desugar
from compiler import *
from standard_elements import *
import unittest

class TestDesugar(unittest.TestCase):

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

    def test_api_para_para(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f[4]"),
            ElementInstance("Forward", "g[4]"),
            Connect("f[i]", "g[i]"),
            APIFunction("identity[i]", "f[i]", "in", "g[i]", "out", "int")
        )
        p = desugar(p)
        g = generate_graph(p, True)
        self.assertEqual(8, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f0','f1','f2','f3']), roots)
        self.assertEqual(set(['f0', 'g0']), self.find_subgraph(g, 'f0', set([])))
        self.assertEqual(set(['f1', 'g1']), self.find_subgraph(g, 'f1', set([])))
        self.assertEqual(set(['f2', 'g2']), self.find_subgraph(g, 'f2', set([])))
        self.assertEqual(set(['f3', 'g3']), self.find_subgraph(g, 'f3', set([])))

    def test_composite(self):
        p = Program(
            Element("Sum",
                    [Port("in", ["int"])],
                    [],
                    r'''this.sum += in(); printf("%d\n", this.sum);''',
                    None,
                    [("Shared", "this")]),
            State("Shared", "int sum;", "100"),
            Composite("Unit",
                      [Port("in", ("sum", "in"))],
                      [], [],
                      [],
                      Program(
                          StateInstance("Shared", "s"),
                          ElementInstance("Sum", "sum", ["s"])
                      )),
            CompositeInstance("Unit", "u[4]")
        )
        p = desugar(p)
        g = generate_graph(p, True)
        self.assertEqual(8, len(g.instances))
        self.assertEqual(4, len(g.state_instances))

    def test_trigger(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f[4]"),
            ElementInstance("Forward", "g[4]"),
            Connect("f[i]", "g[i]"),
            InternalTrigger("g[i]")
        )
        p = desugar(p)
        g = generate_graph(p, True)
        self.assertEqual(16, len(g.instances))
        roots = self.find_roots(g)
        self.assertEqual(set(['f0','f1','f2','f3', '_buffer_g0_read', '_buffer_g1_read', '_buffer_g2_read', '_buffer_g3_read']), roots)

    def test_spec_impl(self):
        p = Program(
            Forward,
            ElementInstance("Forward", "f"),
            ElementInstance("Forward", "g"),
            Spec(
                Connect("f", "g"),
            ),
            Impl(
                Connect("f", "g"),
                ExternalTrigger("g")
            )
        )
        dp = desugar(p, "spec")
        g = generate_graph(dp, True)
        self.assertEqual(2, len(g.instances))
        self.assertEqual(set(['f']), self.find_roots(g))

        dp = desugar(p, "impl")
        g = generate_graph(dp, True)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(set(['f', '_buffer_g_read']), self.find_roots(g))

        dp = desugar(p, "compare")
        g = generate_graph(dp, True)
        self.assertEqual(6, len(g.instances))
        self.assertEqual(set(['_spec_f', '_impl_f', '_buffer__impl_g_read']), self.find_roots(g))

    def test_composite_spec_impl(self):
        p = Program(
            Forward,
            Composite("Unit",
                      [Port("in", ("f", "in"))],
                      [Port("out", ("g", "out"))], [],
                      [],
                      Program(
                          ElementInstance("Forward", "f"),
                          ElementInstance("Forward", "g"),
                          Spec(
                              Connect("f", "g"),
                          ),
                          Impl(
                              Connect("f", "g"),
                              InternalTrigger("g")
                          )
                      )),
            CompositeInstance("Unit", "u")
        )
        dp = desugar(p, "spec")
        g = generate_graph(dp, True)
        self.assertEqual(4, len(g.instances))
        self.assertEqual(set(['u_in']), self.find_roots(g))

        dp = desugar(p, "impl")
        g = generate_graph(dp, True)
        self.assertEqual(6, len(g.instances))
        self.assertEqual(set(['u_in', '_buffer__u_g_read']), self.find_roots(g))

        dp = desugar(p, "compare")
        g = generate_graph(dp, True)
        self.assertEqual(10, len(g.instances))
        self.assertEqual(set(['_spec_u_in', '_impl_u_in', '_buffer__impl_u_g_read']), self.find_roots(g))

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
        dp = desugar(p)
        g = generate_graph(dp)
        all = g.state_instances["all"]
        self.assertEqual("{{&one0,&one1,&one2,&one3}}", all.init)

    def test_init_end2end_another(self):
        p = Program(
            State("One", "int x;"),
            State("Multi", "One* core;"),
            StateInstance("One", "one[4]"),
            StateInstance("Multi", "all[4]", [AddressOf("one[4]")])
        )
        dp = desugar(p)
        g = generate_graph(dp)
        all = g.state_instances["all0"]
        self.assertEqual("{&one0}", all.init)