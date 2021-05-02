import pytest

from django_redis.hash_ring import HashRing


class Node:
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return f"node:{self.id}"

    def __repr__(self):
        return f"<Node {self.id}>"


@pytest.fixture
def hash_ring():
    return HashRing([Node(i) for i in range(3)])


def test_hashring(hash_ring):
    ids = []

    for key in [f"test{x}" for x in range(10)]:
        node = hash_ring.get_node(key)
        ids.append(node.id)

    assert ids == [0, 2, 1, 2, 2, 2, 2, 0, 1, 1]


def test_hashring_brute_force(hash_ring):
    for key in (f"test{x}" for x in range(10000)):
        assert hash_ring.get_node(key)
