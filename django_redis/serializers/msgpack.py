from __future__ import annotations

from typing import Any

import msgpack

from django_redis.serializers.base import BaseSerializer


class MSGPackSerializer(BaseSerializer):
    def dumps(self, value: Any) -> bytes:
        return msgpack.dumps(value)

    def loads(self, value: bytes) -> Any:
        # msgpack 1.0 defaults strict_map_key to True and rejects integer keys
        # that dumps() still writes. Cache values such as {1: "a"} must load.
        return msgpack.loads(value, raw=False, strict_map_key=False)
