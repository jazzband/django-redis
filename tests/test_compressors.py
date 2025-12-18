from typing import ClassVar

import pytest

from django_redis.compressors.base import BaseCompressor
from django_redis.compressors.gzip import GzipCompressor
from django_redis.compressors.identity import IdentityCompressor
from django_redis.exceptions import CompressorError


class BaseCompressorTests:
    """
    Shared contract checks for compressor implementations.
    Subclass this and set compressor_cls to add coverage for a new compressor.
    """

    __test__ = False  # pytest should only run subclasses
    compressor_cls: ClassVar[type[BaseCompressor]] = BaseCompressor
    raises_on_invalid: ClassVar[bool] = True

    @pytest.fixture()
    def compressor(self) -> BaseCompressor:
        return self.compressor_cls({})

    def test_round_trip(self, compressor):
        payload = b"a" * (getattr(compressor, "min_length", 0) + 5)

        compressed = compressor.compress(payload)

        assert compressor.decompress(compressed) == payload

    def test_small_values_are_not_compressed(self, compressor):
        payload = b"a" * getattr(compressor, "min_length", 1)
        assert compressor.compress(payload) == payload

    def test_invalid_payload_raises(self, compressor):
        bad = b"not-a-valid-stream"
        if self.raises_on_invalid:
            with pytest.raises(CompressorError):
                compressor.decompress(bad)
        else:
            assert compressor.decompress(bad) == bad


class TestGzipCompressor(BaseCompressorTests):
    compressor_cls = GzipCompressor

    def test_gzip_is_deterministic(self, compressor):
        payload = b"stable-input" * 2

        first = compressor.compress(payload)
        second = compressor.compress(payload)

        assert first == second


class TestIdentityCompressor(BaseCompressorTests):
    compressor_cls = IdentityCompressor
    raises_on_invalid = False

    def test_identity_always_passthrough(self, compressor):
        payloads = [b"", b"short", b"long" * 10]
        for payload in payloads:
            assert compressor.compress(payload) == payload
            assert compressor.decompress(payload) == payload
