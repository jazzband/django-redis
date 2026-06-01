from __future__ import annotations

from typing import Any


class BaseCompressor:
    def __init__(self, options: dict[str, Any]) -> None:
        self._options = options

    def compress(self, value: bytes) -> bytes:
        raise NotImplementedError

    def decompress(self, value: bytes) -> bytes:
        raise NotImplementedError
