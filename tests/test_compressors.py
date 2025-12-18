import pytest

from django_redis.compressors.gzip import GzipCompressor
from django_redis.exceptions import CompressorError


class BaseCompressorTests:
    """
    Shared contract checks for compressor implementations.
    Subclass this and set compressor_cls to add coverage for a new compressor.
    """

    compressor_cls = None

    @pytest.fixture()
    def compressor(self):
        return self.compressor_cls({})

    def test_round_trip(self, compressor):
        payload = b"a" * (compressor.min_length + 5)

        compressed = compressor.compress(payload)

        # Should actually compress when above min_length.
        assert compressed != payload
        assert compressor.decompress(compressed) == payload

    def test_small_values_are_not_compressed(self, compressor):
        payload = b"a" * compressor.min_length
        assert compressor.compress(payload) == payload

    def test_invalid_payload_raises(self, compressor):
        with pytest.raises(CompressorError):
            compressor.decompress(b"not-a-valid-stream")


class TestGzipCompressor(BaseCompressorTests):
    compressor_cls = GzipCompressor

    def test_gzip_is_deterministic(self, compressor):
        payload = b"stable-input" * 2

        first = compressor.compress(payload)
        second = compressor.compress(payload)

        assert first == second

