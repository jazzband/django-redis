import gzip

from django_redis.compressors.base import BaseCompressor
from django_redis.exceptions import CompressorError


class GzipCompressor(BaseCompressor):
    min_length = 15

    def compress(self, value: bytes) -> bytes:
        if len(value) > self.min_length:
            # Use a fixed mtime so repeated compressions of the same value
            # produce identical bytes (important when the result is used as a key).
            return gzip.compress(value, mtime=0)
        return value

    def decompress(self, value: bytes) -> bytes:
        try:
            return gzip.decompress(value)
        except gzip.BadGzipFile as e:
            raise CompressorError from e
