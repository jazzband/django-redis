"""Tests for sorted set (ZSET) operations in django-redis."""

from django_redis.cache import RedisCache


class TestSortedSetOperations:
    """Tests for sorted set (ZSET) operations."""

    def test_zadd_basic(self, cache: RedisCache):
        """Test adding members to sorted set."""
        result = cache.zadd("scores", {"player1": 100.0, "player2": 200.0})
        assert result == 2
        assert cache.zcard("scores") == 2

    def test_zadd_with_nx(self, cache: RedisCache):
        """Test zadd with nx flag (only add new)."""
        cache.zadd("scores", {"alice": 10.0})
        # Should not update existing
        result = cache.zadd("scores", {"alice": 20.0}, nx=True)
        assert result == 0
        assert cache.zscore("scores", "alice") == 10.0

    def test_zadd_with_xx(self, cache: RedisCache):
        """Test zadd with xx flag (only update existing)."""
        cache.zadd("scores", {"bob": 15.0})
        # Should update existing
        result = cache.zadd("scores", {"bob": 25.0}, xx=True)
        assert result == 0  # No new members added
        assert cache.zscore("scores", "bob") == 25.0
        # Should not add new member
        result = cache.zadd("scores", {"charlie": 30.0}, xx=True)
        assert result == 0
        assert cache.zscore("scores", "charlie") is None

    def test_zadd_with_ch(self, cache: RedisCache):
        """Test zadd with ch flag (return changed count)."""
        cache.zadd("scores", {"player1": 100.0})
        # Update existing member
        result = cache.zadd("scores", {"player1": 150.0, "player2": 200.0}, ch=True)
        assert result == 2  # 1 changed + 1 added

    def test_zcard(self, cache: RedisCache):
        """Test getting sorted set cardinality."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        assert cache.zcard("scores") == 3
        assert cache.zcard("nonexistent") == 0

    def test_zcount(self, cache: RedisCache):
        """Test counting members in score range."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        assert cache.zcount("scores", 2.0, 4.0) == 3  # b, c, d
        assert cache.zcount("scores", "-inf", "+inf") == 5
        assert cache.zcount("scores", 10.0, 20.0) == 0

    def test_zincrby(self, cache: RedisCache):
        """Test incrementing member score."""
        cache.zadd("scores", {"player1": 100.0})
        new_score = cache.zincrby("scores", 50.0, "player1")
        assert new_score == 150.0
        assert cache.zscore("scores", "player1") == 150.0
        # Increment non-existent member
        new_score = cache.zincrby("scores", 25.0, "player2")
        assert new_score == 25.0

    def test_zpopmax(self, cache: RedisCache):
        """Test popping highest scored members."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        # Pop single member
        result = cache.zpopmax("scores")
        assert result == ("c", 3.0)
        assert cache.zcard("scores") == 2
        # Pop multiple members
        cache.zadd("scores", {"d": 4.0, "e": 5.0})
        result = cache.zpopmax("scores", count=2)
        assert len(result) == 2
        assert result[0][0] == "e" and result[0][1] == 5.0
        assert result[1][0] == "d" and result[1][1] == 4.0

    def test_zpopmin(self, cache: RedisCache):
        """Test popping lowest scored members."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        # Pop single member
        result = cache.zpopmin("scores")
        assert result == ("a", 1.0)
        assert cache.zcard("scores") == 2
        # Pop multiple members
        cache.zadd("scores", {"d": 0.5, "e": 0.1})
        result = cache.zpopmin("scores", count=2)
        assert len(result) == 2
        assert result[0][0] == "e" and result[0][1] == 0.1
        assert result[1][0] == "d" and result[1][1] == 0.5

    def test_zrange_basic(self, cache: RedisCache):
        """Test getting range of members by index."""
        cache.zadd("scores", {"alice": 10.0, "bob": 20.0, "charlie": 15.0})
        result = cache.zrange("scores", 0, -1)
        assert result == ["alice", "charlie", "bob"]
        # Get subset
        result = cache.zrange("scores", 0, 1)
        assert result == ["alice", "charlie"]

    def test_zrange_withscores(self, cache: RedisCache):
        """Test zrange with scores."""
        cache.zadd("scores", {"alice": 10.5, "bob": 20.0, "charlie": 15.5})
        result = cache.zrange("scores", 0, -1, withscores=True)
        assert result == [("alice", 10.5), ("charlie", 15.5), ("bob", 20.0)]

    def test_zrange_desc(self, cache: RedisCache):
        """Test zrange in descending order."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        result = cache.zrange("scores", 0, -1, desc=True)
        assert result == ["c", "b", "a"]

    def test_zrangebyscore(self, cache: RedisCache):
        """Test getting members by score range."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        result = cache.zrangebyscore("scores", 2.0, 4.0)
        assert result == ["b", "c", "d"]
        # With infinity
        result = cache.zrangebyscore("scores", "-inf", 2.0)
        assert result == ["a", "b"]

    def test_zrangebyscore_withscores(self, cache: RedisCache):
        """Test zrangebyscore with scores."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        result = cache.zrangebyscore("scores", 1.0, 2.0, withscores=True)
        assert result == [("a", 1.0), ("b", 2.0)]

    def test_zrangebyscore_pagination(self, cache: RedisCache):
        """Test zrangebyscore with pagination."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        result = cache.zrangebyscore("scores", "-inf", "+inf", start=1, num=2)
        assert len(result) == 2
        assert result == ["b", "c"]

    def test_zrank(self, cache: RedisCache):
        """Test getting member rank."""
        cache.zadd("scores", {"alice": 10.0, "bob": 20.0, "charlie": 15.0})
        assert cache.zrank("scores", "alice") == 0  # Lowest score
        assert cache.zrank("scores", "charlie") == 1
        assert cache.zrank("scores", "bob") == 2
        assert cache.zrank("scores", "nonexistent") is None

    def test_zrem(self, cache: RedisCache):
        """Test removing members from sorted set."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        result = cache.zrem("scores", "b")
        assert result == 1
        assert cache.zcard("scores") == 2
        # Remove multiple
        result = cache.zrem("scores", "a", "c")
        assert result == 2
        assert cache.zcard("scores") == 0

    def test_zremrangebyscore(self, cache: RedisCache):
        """Test removing members by score range."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        result = cache.zremrangebyscore("scores", 2.0, 4.0)
        assert result == 3  # b, c, d removed
        assert cache.zcard("scores") == 2
        assert cache.zrange("scores", 0, -1) == ["a", "e"]

    def test_zrevrange(self, cache: RedisCache):
        """Test getting reverse range (highest to lowest)."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        result = cache.zrevrange("scores", 0, -1)
        assert result == ["c", "b", "a"]

    def test_zrevrange_withscores(self, cache: RedisCache):
        """Test zrevrange with scores."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0})
        result = cache.zrevrange("scores", 0, -1, withscores=True)
        assert result == [("c", 3.0), ("b", 2.0), ("a", 1.0)]

    def test_zrevrangebyscore(self, cache: RedisCache):
        """Test getting reverse range by score."""
        cache.zadd("scores", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        # Note: max comes before min in zrevrangebyscore
        result = cache.zrevrangebyscore("scores", 4.0, 2.0)
        assert result == ["d", "c", "b"]

    def test_zscore(self, cache: RedisCache):
        """Test getting member score."""
        cache.zadd("scores", {"alice": 42.5, "bob": 100.0})
        assert cache.zscore("scores", "alice") == 42.5
        assert cache.zscore("scores", "bob") == 100.0
        assert cache.zscore("scores", "nonexistent") is None

    def test_sorted_set_serialization(self, cache: RedisCache):
        """Test that complex objects serialize correctly as members."""
        cache.zadd("complex", {("tuple", "key"): 1.0, "string": 2.0})
        result = cache.zrange("complex", 0, -1)
        # Note: JSON serializer converts tuples to lists
        assert ("tuple", "key") in result or ["tuple", "key"] in result
        assert "string" in result

    def test_sorted_set_version_support(self, cache: RedisCache):
        """Test version parameter works correctly."""
        cache.zadd("data", {"v1": 1.0}, version=1)
        cache.zadd("data", {"v2": 2.0}, version=2)

        assert cache.zcard("data", version=1) == 1
        assert cache.zcard("data", version=2) == 1
        assert cache.zrange("data", 0, -1, version=1) == ["v1"]
        assert cache.zrange("data", 0, -1, version=2) == ["v2"]

    def test_sorted_set_float_scores(self, cache: RedisCache):
        """Test that float scores work correctly."""
        cache.zadd("precise", {"a": 1.1, "b": 1.2, "c": 1.15})
        result = cache.zrange("precise", 0, -1, withscores=True)
        assert result[0] == ("a", 1.1)
        assert result[1] == ("c", 1.15)
        assert result[2] == ("b", 1.2)

    def test_sorted_set_negative_scores(self, cache: RedisCache):
        """Test that negative scores work correctly."""
        cache.zadd("temps", {"freezing": -10.0, "cold": 0.0, "warm": 20.0})
        result = cache.zrange("temps", 0, -1)
        assert result == ["freezing", "cold", "warm"]

    def test_zpopmin_empty_set(self, cache: RedisCache):
        """Test zpopmin on empty sorted set."""
        result = cache.zpopmin("nonexistent")
        assert result is None
        result = cache.zpopmin("nonexistent", count=5)
        assert result == []

    def test_zpopmax_empty_set(self, cache: RedisCache):
        """Test zpopmax on empty sorted set."""
        result = cache.zpopmax("nonexistent")
        assert result is None
        result = cache.zpopmax("nonexistent", count=5)
        assert result == []
