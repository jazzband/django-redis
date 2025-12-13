from django_redis.cache import RedisCache


class TestListOperations:
    """Tests for Redis list operations."""

    def test_lpush_rpush(self, cache: RedisCache):
        """Test pushing elements to list from left and right."""
        # Push to left (head)
        count = cache.lpush("mylist", "value1")
        assert count == 1

        count = cache.lpush("mylist", "value2", "value3")
        assert count == 3

        # Push to right (tail)
        count = cache.rpush("mylist", "value4")
        assert count == 4

        # Verify order: [value3, value2, value1, value4]
        result = cache.lrange("mylist", 0, -1)
        assert result == ["value3", "value2", "value1", "value4"]

    def test_lpop_rpop(self, cache: RedisCache):
        """Test popping elements from list."""
        # Setup list: [1, 2, 3]
        cache.rpush("mylist", "1", "2", "3")

        # Pop from left
        value = cache.lpop("mylist")
        assert value == "1"

        # Pop from right
        value = cache.rpop("mylist")
        assert value == "3"

        # Only 2 should remain
        result = cache.lrange("mylist", 0, -1)
        assert result == ["2"]

        # Pop from empty list
        cache.lpop("mylist")
        value = cache.lpop("mylist")
        assert value is None

    def test_lpop_rpop_with_count(self, cache: RedisCache):
        """Test popping multiple elements with count parameter."""
        # Setup list: [1, 2, 3, 4, 5]
        cache.rpush("mylist", "1", "2", "3", "4", "5")

        # Pop 2 from left
        values = cache.lpop("mylist", count=2)
        assert values == ["1", "2"]

        # Pop 2 from right
        values = cache.rpop("mylist", count=2)
        assert values == ["5", "4"]

        # Only 3 should remain
        result = cache.lrange("mylist", 0, -1)
        assert result == ["3"]

    def test_lrange(self, cache: RedisCache):
        """Test getting range of elements."""
        cache.rpush("mylist", "1", "2", "3", "4", "5")

        # Get all elements
        result = cache.lrange("mylist", 0, -1)
        assert result == ["1", "2", "3", "4", "5"]

        # Get first 3 elements
        result = cache.lrange("mylist", 0, 2)
        assert result == ["1", "2", "3"]

        # Get last 2 elements
        result = cache.lrange("mylist", -2, -1)
        assert result == ["4", "5"]

        # Get middle elements
        result = cache.lrange("mylist", 1, 3)
        assert result == ["2", "3", "4"]

    def test_lindex(self, cache: RedisCache):
        """Test getting element at specific index."""
        cache.rpush("mylist", "a", "b", "c", "d")

        # Get by positive index
        assert cache.lindex("mylist", 0) == "a"
        assert cache.lindex("mylist", 2) == "c"

        # Get by negative index
        assert cache.lindex("mylist", -1) == "d"
        assert cache.lindex("mylist", -2) == "c"

        # Out of range
        assert cache.lindex("mylist", 10) is None
        assert cache.lindex("mylist", -10) is None

        # Non-existent key
        assert cache.lindex("nonexistent", 0) is None

    def test_llen(self, cache: RedisCache):
        """Test getting length of list."""
        # Empty/non-existent list
        assert cache.llen("mylist") == 0

        # Add elements
        cache.rpush("mylist", "1", "2", "3")
        assert cache.llen("mylist") == 3

        cache.rpush("mylist", "4", "5")
        assert cache.llen("mylist") == 5

        # After popping
        cache.lpop("mylist")
        assert cache.llen("mylist") == 4

    def test_lrem(self, cache: RedisCache):
        """Test removing elements from list."""
        # Setup list with duplicates
        cache.rpush("mylist", "a", "b", "a", "c", "a", "d")

        # Remove first 2 occurrences of 'a' from head
        count = cache.lrem("mylist", 2, "a")
        assert count == 2
        result = cache.lrange("mylist", 0, -1)
        assert result == ["b", "c", "a", "d"]

        # Remove all remaining occurrences of 'a'
        count = cache.lrem("mylist", 0, "a")
        assert count == 1
        result = cache.lrange("mylist", 0, -1)
        assert result == ["b", "c", "d"]

        # Remove non-existent value
        count = cache.lrem("mylist", 1, "z")
        assert count == 0

    def test_lrem_negative_count(self, cache: RedisCache):
        """Test lrem with negative count (remove from tail)."""
        # Setup list: [a, b, a, c, a]
        cache.rpush("mylist", "a", "b", "a", "c", "a")

        # Remove last 2 occurrences of 'a' from tail
        count = cache.lrem("mylist", -2, "a")
        assert count == 2
        result = cache.lrange("mylist", 0, -1)
        assert result == ["a", "b", "c"]

    def test_ltrim(self, cache: RedisCache):
        """Test trimming list to specified range."""
        cache.rpush("mylist", "1", "2", "3", "4", "5")

        # Trim to middle elements
        result = cache.ltrim("mylist", 1, 3)
        assert result is True

        # Verify trimmed list
        trimmed = cache.lrange("mylist", 0, -1)
        assert trimmed == ["2", "3", "4"]

    def test_ltrim_with_negative_indices(self, cache: RedisCache):
        """Test ltrim with negative indices."""
        cache.rpush("mylist", "1", "2", "3", "4", "5")

        # Keep last 3 elements
        cache.ltrim("mylist", -3, -1)
        result = cache.lrange("mylist", 0, -1)
        assert result == ["3", "4", "5"]

    def test_lset(self, cache: RedisCache):
        """Test setting element at specific index."""
        cache.rpush("mylist", "a", "b", "c", "d")

        # Set by positive index
        result = cache.lset("mylist", 0, "A")
        assert result is True
        assert cache.lindex("mylist", 0) == "A"

        result = cache.lset("mylist", 2, "C")
        assert result is True
        assert cache.lindex("mylist", 2) == "C"

        # Set by negative index
        result = cache.lset("mylist", -1, "D")
        assert result is True
        assert cache.lindex("mylist", -1) == "D"

        # Verify final list
        final = cache.lrange("mylist", 0, -1)
        assert final == ["A", "b", "C", "D"]

    def test_list_with_complex_objects(self, cache: RedisCache):
        """Test list operations with complex Python objects."""
        obj1 = {"name": "Alice", "age": 30}
        obj2 = {"name": "Bob", "age": 25}
        obj3 = ["item1", "item2", 123]

        # Push complex objects
        cache.rpush("mylist", obj1, obj2, obj3)

        # Retrieve and verify
        result = cache.lrange("mylist", 0, -1)
        assert result == [obj1, obj2, obj3]

        # Verify individual access
        assert cache.lindex("mylist", 0) == obj1
        assert cache.lindex("mylist", 1) == obj2

        # Pop and verify
        popped = cache.rpop("mylist")
        assert popped == obj3

    def test_list_with_version(self, cache: RedisCache):
        """Test list operations with version parameter."""
        # Use different versions
        cache.rpush("mylist", "v1_value", version=1)
        cache.rpush("mylist", "v2_value", version=2)

        # Verify values are separate
        result_v1 = cache.lrange("mylist", 0, -1, version=1)
        result_v2 = cache.lrange("mylist", 0, -1, version=2)

        assert result_v1 == ["v1_value"]
        assert result_v2 == ["v2_value"]

    def test_empty_list_operations(self, cache: RedisCache):
        """Test operations on empty or non-existent lists."""
        # Operations on non-existent list
        assert cache.llen("nonexistent") == 0
        assert cache.lrange("nonexistent", 0, -1) == []
        assert cache.lindex("nonexistent", 0) is None
        assert cache.lpop("nonexistent") is None
        assert cache.rpop("nonexistent") is None

        # lpop/rpop with count on non-existent list
        assert cache.lpop("nonexistent", count=5) is None
        assert cache.rpop("nonexistent", count=5) is None

    def test_list_queue_pattern(self, cache: RedisCache):
        """Test using list as a queue (FIFO)."""
        # Enqueue: push to tail
        cache.rpush("queue", "task1", "task2", "task3")

        # Dequeue: pop from head
        task = cache.lpop("queue")
        assert task == "task1"

        task = cache.lpop("queue")
        assert task == "task2"

        # Queue should have one item left
        assert cache.llen("queue") == 1

    def test_list_stack_pattern(self, cache: RedisCache):
        """Test using list as a stack (LIFO)."""
        # Push to stack
        cache.rpush("stack", "item1", "item2", "item3")

        # Pop from stack
        item = cache.rpop("stack")
        assert item == "item3"

        item = cache.rpop("stack")
        assert item == "item2"

        # Stack should have one item left
        assert cache.llen("stack") == 1
        assert cache.lindex("stack", 0) == "item1"
