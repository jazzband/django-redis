"""Tests for async cache operations."""

import asyncio

import pytest

from django_redis.cache import RedisCache

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
class TestAsyncOperations:
    async def test_aget_aset(self, cache: RedisCache):
        await cache.aset("test_key", "test_value", timeout=30)
        result = await cache.aget("test_key")
        assert result == "test_value"

    async def test_aget_default(self, cache: RedisCache):
        result = await cache.aget("nonexistent_key", default="default_value")
        assert result == "default_value"

    async def test_adelete(self, cache: RedisCache):
        await cache.aset("key_to_delete", "value", timeout=30)
        assert await cache.ahas_key("key_to_delete") is True

        result = await cache.adelete("key_to_delete")
        assert result == 1
        assert await cache.ahas_key("key_to_delete") is False

    async def test_ahas_key(self, cache: RedisCache):
        assert await cache.ahas_key("nonexistent_key") is False

        await cache.aset("existing_key", "value", timeout=30)
        assert await cache.ahas_key("existing_key") is True

    async def test_aset_with_timeout(self, cache: RedisCache):
        await cache.aset("timeout_key", "value", timeout=1)
        assert await cache.aget("timeout_key") == "value"

        await asyncio.sleep(1.1)
        assert await cache.aget("timeout_key") is None

    async def test_aset_nx(self, cache: RedisCache):
        result = await cache.aset("nx_key", "first_value", timeout=30, nx=True)
        assert result is True

        result = await cache.aset("nx_key", "second_value", timeout=30, nx=True)
        assert result is False
        assert await cache.aget("nx_key") == "first_value"

    async def test_async_with_versioning(self, cache: RedisCache):
        await cache.aset("versioned_key", "value_v1", timeout=30, version=1)
        await cache.aset("versioned_key", "value_v2", timeout=30, version=2)

        assert await cache.aget("versioned_key", version=1) == "value_v1"
        assert await cache.aget("versioned_key", version=2) == "value_v2"

    async def test_async_complex_objects(self, cache: RedisCache):
        test_dict = {
            "key1": "value1",
            "key2": [1, 2, 3],
            "key3": {"nested": "dict"},
        }

        await cache.aset("complex_key", test_dict, timeout=30)
        result = await cache.aget("complex_key")

        assert result == test_dict
        assert isinstance(result, dict)
        assert result["key2"] == [1, 2, 3]

    async def test_aadd(self, cache: RedisCache):
        result = await cache.aadd("add_key", "value", timeout=30)
        assert result is True

        result = await cache.aadd("add_key", "other_value", timeout=30)
        assert result is False
        assert await cache.aget("add_key") == "value"

    async def test_adelete_many(self, cache: RedisCache):
        await cache.aset("key1", "value1", timeout=30)
        await cache.aset("key2", "value2", timeout=30)
        await cache.aset("key3", "value3", timeout=30)

        result = await cache.adelete_many(["key1", "key2", "key3"])
        assert result == 3
        assert await cache.ahas_key("key1") is False
        assert await cache.ahas_key("key2") is False

    async def test_aget_many(self, cache: RedisCache):
        await cache.aset("key1", "value1", timeout=30)
        await cache.aset("key2", "value2", timeout=30)

        result = await cache.aget_many(["key1", "key2", "key3"])
        assert result == {"key1": "value1", "key2": "value2"}

    async def test_aset_many(self, cache: RedisCache):
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        await cache.aset_many(data, timeout=30)

        assert await cache.aget("key1") == "value1"
        assert await cache.aget("key2") == "value2"
        assert await cache.aget("key3") == "value3"

    async def test_atouch(self, cache: RedisCache):
        await cache.aset("touch_key", "value", timeout=30)
        result = await cache.atouch("touch_key", timeout=60)
        assert result is True

    async def test_aincr(self, cache: RedisCache):
        await cache.aset("counter", 10, timeout=30)
        result = await cache.aincr("counter", delta=5)
        assert result == 15
        assert await cache.aget("counter") == 15

    async def test_adecr(self, cache: RedisCache):
        await cache.aset("counter", 10, timeout=30)
        result = await cache.adecr("counter", delta=3)
        assert result == 7
        assert await cache.aget("counter") == 7

    async def test_aclear(self, cache: RedisCache):
        await cache.aset("key1", "value1", timeout=30)
        await cache.aset("key2", "value2", timeout=30)

        await cache.aclear()
        assert await cache.aget("key1") is None
        assert await cache.aget("key2") is None

    async def test_aincr_nonexistent_key(self, cache: RedisCache):
        """Test that aincr raises ValueError for non-existent key."""
        with pytest.raises(ValueError, match="not found"):
            await cache.aincr("nonexistent_counter", delta=5)

    async def test_attl(self, cache: RedisCache):
        """Test async ttl method."""
        await cache.aset("ttl_key", "value", timeout=60)
        ttl = await cache.attl("ttl_key")
        assert ttl is not None
        assert ttl > 0 and ttl <= 60
