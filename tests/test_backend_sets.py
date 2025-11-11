import pytest

from django_redis.cache import RedisCache


class TestSetOperations:
    """Tests for Redis set operations."""

    def test_sadd_basic(self, cache: RedisCache):
        """Test adding members to set."""
        result = cache.sadd("colors", "red", "blue", "green")
        assert result == 3
        assert cache.scard("colors") == 3

    def test_sadd_duplicate(self, cache: RedisCache):
        """Test adding duplicate members (should not increase size)."""
        cache.sadd("colors", "red", "blue")
        result = cache.sadd("colors", "red")
        assert result == 0
        assert cache.scard("colors") == 2

    def test_scard(self, cache: RedisCache):
        """Test getting set cardinality."""
        cache.sadd("numbers", "1", "2", "3")
        assert cache.scard("numbers") == 3
        assert cache.scard("nonexistent") == 0

    def test_sismember(self, cache: RedisCache):
        """Test checking if member exists in set."""
        cache.sadd("fruits", "apple", "banana", "orange")
        assert cache.sismember("fruits", "apple") is True
        assert cache.sismember("fruits", "grape") is False

    def test_smembers(self, cache: RedisCache):
        """Test getting all members from set."""
        cache.sadd("letters", "a", "b", "c")
        members = cache.smembers("letters")
        assert isinstance(members, set)
        assert members == {"a", "b", "c"}

    def test_srem(self, cache: RedisCache):
        """Test removing members from set."""
        cache.sadd("items", "x", "y", "z")
        result = cache.srem("items", "y")
        assert result == 1
        assert cache.scard("items") == 2
        result = cache.srem("items", "x", "z")
        assert result == 2
        assert cache.scard("items") == 0

    def test_spop(self, cache: RedisCache):
        """Test popping random member from set."""
        cache.sadd("deck", "ace", "king", "queen")
        result = cache.spop("deck")
        assert result in {"ace", "king", "queen"}
        assert cache.scard("deck") == 2

    def test_spop_with_count(self, cache: RedisCache):
        """Test popping multiple random members."""
        cache.sadd("deck", "ace", "king", "queen", "jack")
        result = cache.spop("deck", count=2)
        assert isinstance(result, set)
        assert len(result) == 2
        assert cache.scard("deck") == 2

    def test_srandmember(self, cache: RedisCache):
        """Test getting random member without removing."""
        cache.sadd("cards", "ace", "king", "queen")
        result = cache.srandmember("cards")
        assert result in {"ace", "king", "queen"}
        assert cache.scard("cards") == 3

    def test_srandmember_with_count(self, cache: RedisCache):
        """Test getting multiple random members."""
        cache.sadd("cards", "ace", "king", "queen", "jack")
        result = cache.srandmember("cards", count=2)
        assert isinstance(result, list)
        assert len(result) == 2
        assert cache.scard("cards") == 4

    def test_sdiff(self, cache: RedisCache):
        """Test set difference operation."""
        cache.sadd("set1", "a", "b", "c", "d")
        cache.sadd("set2", "c", "d", "e", "f")
        result = cache.sdiff("set1", "set2")
        assert result == {"a", "b"}

    def test_sdiffstore(self, cache: RedisCache):
        """Test storing set difference."""
        cache.sadd("set1", "a", "b", "c")
        cache.sadd("set2", "b", "c", "d")
        result = cache.sdiffstore("result", "set1", "set2")
        assert result == 1
        assert cache.smembers("result") == {"a"}

    def test_sinter(self, cache: RedisCache):
        """Test set intersection operation."""
        cache.sadd("set1", "a", "b", "c")
        cache.sadd("set2", "b", "c", "d")
        result = cache.sinter("set1", "set2")
        assert result == {"b", "c"}

    def test_sinterstore(self, cache: RedisCache):
        """Test storing set intersection."""
        cache.sadd("set1", "a", "b", "c")
        cache.sadd("set2", "b", "c", "d")
        result = cache.sinterstore("result", "set1", "set2")
        assert result == 2
        assert cache.smembers("result") == {"b", "c"}

    def test_sunion(self, cache: RedisCache):
        """Test set union operation."""
        cache.sadd("set1", "a", "b")
        cache.sadd("set2", "b", "c")
        result = cache.sunion("set1", "set2")
        assert result == {"a", "b", "c"}

    def test_sunionstore(self, cache: RedisCache):
        """Test storing set union."""
        cache.sadd("set1", "a", "b")
        cache.sadd("set2", "b", "c")
        result = cache.sunionstore("result", "set1", "set2")
        assert result == 3
        assert cache.smembers("result") == {"a", "b", "c"}

    def test_smove(self, cache: RedisCache):
        """Test moving member between sets."""
        cache.sadd("source", "a", "b", "c")
        cache.sadd("dest", "x", "y")
        result = cache.smove("source", "dest", "b")
        assert result is True
        assert cache.smembers("source") == {"a", "c"}
        assert cache.smembers("dest") == {"x", "y", "b"}

    def test_smove_nonexistent_member(self, cache: RedisCache):
        """Test moving non-existent member."""
        cache.sadd("source", "a", "b")
        cache.sadd("dest", "x")
        result = cache.smove("source", "dest", "z")
        assert result is False

    def test_smismember(self, cache: RedisCache):
        """Test checking multiple members at once."""
        cache.sadd("items", "apple", "banana", "orange")
        result = cache.smismember("items", "apple", "grape", "banana")
        assert result == [True, False, True]

    def test_sscan(self, cache: RedisCache):
        """Test scanning set members."""
        cache.sadd("dataset", "item1", "item2", "item3")
        result = cache.sscan("dataset")
        assert isinstance(result, set)
        assert len(result) <= 3

    def test_sscan_iter(self, cache: RedisCache):
        """Test iterating over set members."""
        cache.sadd("dataset", "a", "b", "c", "d", "e")
        members = list(cache.sscan_iter("dataset"))
        assert len(members) == 5
        assert set(members) == {"a", "b", "c", "d", "e"}

    def test_set_with_version(self, cache: RedisCache):
        """Test set operations with version parameter."""
        cache.sadd("data", "v1", version=1)
        cache.sadd("data", "v2", version=2)

        assert cache.smembers("data", version=1) == {"v1"}
        assert cache.smembers("data", version=2) == {"v2"}

    def test_set_with_complex_objects(self, cache: RedisCache):
        """Test that complex objects serialize correctly."""
        cache.sadd("complex", ("tuple", "key"), "string", 123)
        members = cache.smembers("complex")
        assert "string" in members
        assert 123 in members
        assert len(members) == 3

    def test_empty_set_operations(self, cache: RedisCache):
        """Test operations on empty/non-existent sets."""
        assert cache.scard("nonexistent") == 0
        assert cache.smembers("nonexistent") == set()
        assert cache.sismember("nonexistent", "anything") is False
        assert cache.spop("nonexistent") is None

    def test_multiple_set_operations(self, cache: RedisCache):
        """Test combining multiple set operations."""
        cache.sadd("set1", "a", "b", "c")
        cache.sadd("set2", "b", "c", "d")
        cache.sadd("set3", "c", "d", "e")

        result = cache.sunion("set1", "set2", "set3")
        assert result == {"a", "b", "c", "d", "e"}

        result = cache.sinter("set1", "set2", "set3")
        assert result == {"c"}

    def test_sscan_with_match(self, cache: RedisCache):
        """Test sscan with match - raises error with compression, works without."""
        cache.sadd("testset", "item1", "item2", "item3", "other")

        if cache.client._has_compression_enabled():
            with pytest.raises(
                ValueError,
                match="Using match with compression is not supported",
            ):
                cache.sscan("testset", match="item*")
        else:
            result = cache.sscan("testset", match="item*")
            assert isinstance(result, set)
            assert all(item.startswith("item") for item in result)

    def test_sscan_iter_with_match(self, cache: RedisCache):
        """Test sscan_iter with match - raises error with compression, works without."""
        cache.sadd("testset", "item1", "item2", "item3", "other")

        if cache.client._has_compression_enabled():
            with pytest.raises(
                ValueError,
                match="Using match with compression is not supported",
            ):
                list(cache.sscan_iter("testset", match="item*"))
        else:
            result = list(cache.sscan_iter("testset", match="item*"))
            assert len(result) >= 3
            assert all(item.startswith("item") for item in result)
