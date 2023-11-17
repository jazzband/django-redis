import gzip

from ..exceptions import CompressorError
from .base import BaseCompressor


class GzipCompressor(BaseCompressor):
    min_length = 15

    def compress(self, value: bytes) -> bytes:
        if len(value) > self.min_length:
            return gzip.compress(value)
        return value

    def decompress(self, value: bytes) -> bytes:
        try:
            return gzip.decompress(value)
        except gzip.BadGzipFile as e:
            raise CompressorError from e
