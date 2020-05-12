from typing import Any


class BaseSerializer:
    def dumps(self, value: Any) -> bytes:
        raise NotImplementedError

    def loads(self, value: bytes) -> Any:
        raise NotImplementedError
