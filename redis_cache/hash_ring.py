# -*- coding: utf-8 -*-

import zlib
import bisect

class HashRing(object):
    def __init__(self, nodes=[], replicas=128):
        self.nodes = nodes
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []

        for node in nodes:
            self.add_node(node)

    def add_node(self, node):
        self.nodes.append(node)

        for x in xrange(self.replicas):
            crckey = zlib.crc32("%s:%d" % (node, x))
            self.ring[crckey] = node
            self.sorted_keys.append(crckey)

        self.sorted_keys.sort()

    def remove_node(self, node):
        self.nodes.remove(node)
        for x in xrange(self.replicas):
            crckey = zlib.crc32("%s:%d" % (node, x))
            self.ring.remove(crckey)
            self.sorted_keys.remove(crckey)

    def get_node(self, key):
        n, i = self.get_node_pos(key)
        return n

    def get_node_pos(self, key):
        if len(self.ring) == 0:
            return (None, None)
        
        crc = zlib.crc32(key)
        idx = bisect.bisect(self.sorted_keys, crc)
        idx = min(idx, (self.replicas * len(self.nodes))-1)
        return (self.ring[self.sorted_keys[idx]], idx)

    def iter_nodes(self, key):
        if len(self.ring) == 0: yield None, None
        node, pos = self.get_node_pos(key)
        for k in self.sorted_keys[pos:]:
            yield k, self.ring[k]

    def __call__(self, key):
        return self.get_node(key)
