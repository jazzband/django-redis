from __future__ import annotations

from lz4.frame import compress as _compress, decompress as _decompress

from django_redis.compressors.base import BaseCompressor
from django_redis.exceptions import CompressorError


class Lz4Compressor(BaseCompressor):
    min_length = 15

    def compress(self, value: bytes) -> bytes:
        if len(value) > self.min_length:
            return _compress(value)  # type: ignore[no-any-return]
        return value

    def decompress(self, value: bytes) -> bytes:
        try:
            return _decompress(value)  # type: ignore[no-any-return]
        except Exception as e:
            raise CompressorError from e
