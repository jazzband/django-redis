from lz4.frame import (  # type: ignore
    compress as _compress, decompress as _decompress,
)

from ..exceptions import CompressorError
from .base import BaseCompressor


class Lz4Compressor(BaseCompressor):
    min_length = 15

    def compress(self, value: bytes) -> bytes:
        if len(value) > self.min_length:
            return _compress(value)
        return value

    def decompress(self, value: bytes) -> bytes:
        try:
            return _decompress(value)
        except Exception as e:
            raise CompressorError(e)
