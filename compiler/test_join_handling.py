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