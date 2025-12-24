import pytest

from django_redis.cache import RedisCache
from django_redis.client import ShardClient


class TestHashOperations:
    """Tests for Redis hash operations."""

    def test_hset(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")
        cache.hset("foo_hash1", "foo1", "bar1")
        cache.hset("foo_hash1", "foo2", "bar2")
        assert cache.hlen("foo_hash1") == 2
        assert cache.hexists("foo_hash1", "foo1")
        assert cache.hexists("foo_hash1", "foo2")

    def test_hdel(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")
        cache.hset("foo_hash2", "foo1", "bar1")
        cache.hset("foo_hash2", "foo2", "bar2")
        assert cache.hlen("foo_hash2") == 2
        deleted_count = cache.hdel("foo_hash2", "foo1")
        assert deleted_count == 1
        assert cache.hlen("foo_hash2") == 1
        assert not cache.hexists("foo_hash2", "foo1")
        assert cache.hexists("foo_hash2", "foo2")

    def test_hlen(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")
        assert cache.hlen("foo_hash3") == 0
        cache.hset("foo_hash3", "foo1", "bar1")
        assert cache.hlen("foo_hash3") == 1
        cache.hset("foo_hash3", "foo2", "bar2")
        assert cache.hlen("foo_hash3") == 2

    def test_hkeys(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")
        cache.hset("foo_hash4", "foo1", "bar1")
        cache.hset("foo_hash4", "foo2", "bar2")
        cache.hset("foo_hash4", "foo3", "bar3")
        keys = cache.hkeys("foo_hash4")
        assert len(keys) == 3
        for i in range(len(keys)):
            assert keys[i] == f"foo{i + 1}"

    def test_hexists(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")
        cache.hset("foo_hash5", "foo1", "bar1")
        assert cache.hexists("foo_hash5", "foo1")
        assert not cache.hexists("foo_hash5", "foo")

    def test_hash_version_support(self, cache: RedisCache):
        """Test that version parameter works correctly for hash methods."""
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        # Set values with different versions
        cache.hset("my_hash", "field1", "value1", version=1)
        cache.hset("my_hash", "field2", "value2", version=1)
        cache.hset("my_hash", "field1", "different_value", version=2)

        # Verify both versions exist independently
        assert cache.hexists("my_hash", "field1", version=1)
        assert cache.hexists("my_hash", "field2", version=1)
        assert cache.hexists("my_hash", "field1", version=2)
        assert not cache.hexists("my_hash", "field2", version=2)

        # Verify hlen works with versions
        assert cache.hlen("my_hash", version=1) == 2
        assert cache.hlen("my_hash", version=2) == 1

        # Verify hkeys works with versions
        keys_v1 = cache.hkeys("my_hash", version=1)
        assert len(keys_v1) == 2
        assert "field1" in keys_v1
        assert "field2" in keys_v1

        keys_v2 = cache.hkeys("my_hash", version=2)
        assert len(keys_v2) == 1
        assert "field1" in keys_v2

        # Verify hdel works with versions
        cache.hdel("my_hash", "field1", version=1)
        assert not cache.hexists("my_hash", "field1", version=1)
        assert cache.hexists("my_hash", "field1", version=2)  # v2 should still exist

    def test_hash_key_structure_in_redis(self, cache: RedisCache):
        """Test that hash keys are prefixed but fields are not."""
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        # Get raw Redis client
        client = cache.client.get_client(write=False)

        # Set some hash data
        cache.hset("user:1000", "email", "alice@example.com", version=2)
        cache.hset("user:1000", "name", "Alice", version=2)

        # Get the actual Redis key that was created
        expected_key = cache.client.make_key("user:1000", version=2)

        # Verify the hash exists in Redis with the prefixed key
        assert client.exists(expected_key)
        assert client.type(expected_key) == b"hash"

        # Verify fields are stored WITHOUT prefix
        actual_fields = client.hkeys(expected_key)
        # Fields should be plain "email" and "name", not prefixed
        assert b"email" in actual_fields
        assert b"name" in actual_fields

        # Verify field values are correct
        assert client.hget(expected_key, b"email") is not None
        assert client.hget(expected_key, b"name") is not None
