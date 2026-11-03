from __future__ import annotations

from django_redis.serializers.msgpack import MSGPackSerializer


def test_msgpack_loads_integer_map_keys():
    serializer = MSGPackSerializer({})
    payload = serializer.dumps({1: "a", "b": 2})
    assert serializer.loads(payload) == {1: "a", "b": 2}
