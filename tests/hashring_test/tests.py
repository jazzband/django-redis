# -*- coding: utf-8 -*-

from django.test import TestCase

from django_redis.hash_ring import HashRing


class Node(object):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return "node:{0}".format(self.id)

    def __repr__(self):
        return "<Node {}>".format(self.id)


class HashRingTest(TestCase):
    def setUp(self):
        self.node0 = Node(0)
        self.node1 = Node(1)
        self.node2 = Node(2)

        self.nodes = [self.node0, self.node1, self.node2]
        self.ring = HashRing(self.nodes)

    def test_hashring(self):
        ids = []

        for key in ["test{0}".format(x) for x in range(10)]:
            node = self.ring.get_node(key)
            ids.append(node.id)

        self.assertEqual(ids, [0, 2, 1, 2, 2, 2, 2, 0, 1, 1])

    def test_hashring_brute_force(self):
        for key in ("test{0}".format(x) for x in range(10000)):
            node = self.ring.get_node(key)
