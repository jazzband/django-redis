from typing import Any


class BaseSerializer:
    def dumps(self, value) -> bytes:
        raise NotImplementedError

    def loads(self, value) -> Any:
        raise NotImplementedError
