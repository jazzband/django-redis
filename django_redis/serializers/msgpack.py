from typing import Any

import msgpack

from .base import BaseSerializer


class MSGPackSerializer(BaseSerializer):
    def dumps(self, value) -> bytes:
        return msgpack.dumps(value)

    def loads(self, value) -> Any:
        return msgpack.loads(value, raw=False)
