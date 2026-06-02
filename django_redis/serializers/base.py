from __future__ import annotations

from typing import Any


class BaseSerializer:
    def __init__(self, options: dict[str, Any]) -> None:
        pass

    def dumps(self, value: Any) -> bytes:
        raise NotImplementedError

    def loads(self, value: bytes) -> Any:
        raise NotImplementedError
