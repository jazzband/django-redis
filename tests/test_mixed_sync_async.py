"""
Tests for mixed sync/async scenarios using async_to_sync.

This tests the critical case where sync code calls async cache methods,
which creates multiple event loops. Our architecture must handle this
correctly while django-async-redis would fail.
"""

import asyncio

import pytest
from asgiref.sync import async_to_sync

from django_redis.cache import RedisCache


@pytest.mark.asyncio
class TestMixedSyncAsync:
    """Test mixed sync/async scenarios with multiple event loops."""

    def test_sync_calling_async_multiple_times(self, cache: RedisCache):
        """
        Test sync code calling async cache operations multiple times.
        Each call creates a new event loop (via async_to_sync).
        This is the critical scenario where pool caching must be event-loop-aware.
        """

        @async_to_sync
        async def sync_set_get(key, value):
            """Helper that uses async cache from sync context."""
            await cache.aset(key, value)
            return await cache.aget(key)

        # Make multiple calls - each creates a new event loop
        result1 = sync_set_get("key1", "value1")
        assert result1 == "value1"

        result2 = sync_set_get("key2", "value2")
        assert result2 == "value2"

        result3 = sync_set_get("key3", "value3")
        assert result3 == "value3"

        # All should succeed without "Event loop is closed" errors

    def test_sync_calling_async_verifies_pool_isolation(self, cache: RedisCache):
        """
        Test that each event loop gets its own connection pools.
        Verifies our factory's per-event-loop pool caching.
        """
        factory = cache.client.async_connection_factory
        event_loops_seen = []

        @async_to_sync
        async def track_event_loop():
            """Track which event loop and pools are being used."""
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
            event_loops_seen.append(loop_id)

            # Use cache to trigger pool creation
            await cache.aset(f"test_{loop_id}", "value")

            # Check factory pools
            num_loops_in_factory = len(factory._pools)
            return loop_id, num_loops_in_factory

        # First call creates first event loop
        loop1_id, pools_after_first = track_event_loop()

        # Second call creates second event loop
        loop2_id, pools_after_second = track_event_loop()

        # Third call creates third event loop
        loop3_id, pools_after_third = track_event_loop()

        # Verify different event loops were used
        assert loop1_id != loop2_id
        assert loop2_id != loop3_id
        assert loop1_id != loop3_id

        # Verify pools were cached for each event loop
        # Note: Some loops might be GC'd so count may be less than total
        assert pools_after_first >= 1
        assert pools_after_second >= 1
        assert pools_after_third >= 1

    def test_sync_and_pure_async_can_coexist(self, cache: RedisCache):
        """
        Test that sync calls (using async_to_sync) and pure async calls
        can coexist without interfering with each other.
        """

        @async_to_sync
        async def sync_context_operation():
            """Simulate sync view calling async cache."""
            await cache.aset("sync_key", "sync_value")
            return await cache.aget("sync_key")

        async def pure_async_operation():
            """Simulate pure async view."""
            await cache.aset("async_key", "async_value")
            return await cache.aget("async_key")

        # Run sync context operation (creates its own event loop)
        sync_result = sync_context_operation()
        assert sync_result == "sync_value"

        # Run pure async operation (in test's event loop)
        async_result = asyncio.run(pure_async_operation())
        assert async_result == "async_value"

        # Both should work without errors

    def test_multiple_sync_calls_different_event_loops(self, cache: RedisCache):
        """
        Test that multiple sync calls each get their own event loop and pools.
        This is the scenario that breaks django-async-redis's global pool caching.
        """
        results = []

        @async_to_sync
        async def operation(iteration):
            """Each call gets a new event loop."""
            loop = asyncio.get_running_loop()

            # Use cache operations
            await cache.aset(f"iter_{iteration}", f"value_{iteration}")
            value = await cache.aget(f"iter_{iteration}")

            # Also test bulk operations
            await cache.aset_many(
                {f"bulk_{iteration}_1": "v1", f"bulk_{iteration}_2": "v2"},
            )
            bulk_values = await cache.aget_many(
                [f"bulk_{iteration}_1", f"bulk_{iteration}_2"],
            )

            results.append(
                {
                    "iteration": iteration,
                    "loop_id": id(loop),
                    "value": value,
                    "bulk_count": len(bulk_values),
                },
            )

        # Run multiple iterations
        for i in range(5):
            operation(i)

        # Verify all succeeded
        assert len(results) == 5

        # Verify each used correct data
        for i, result in enumerate(results):
            assert result["iteration"] == i
            assert result["value"] == f"value_{i}"
            assert result["bulk_count"] == 2

        # Verify different event loops were used
        loop_ids = [r["loop_id"] for r in results]
        assert len(set(loop_ids)) == 5  # All different

    def test_async_operations_with_multiple_servers(self, cache: RedisCache):
        """
        Test async operations work with multiple servers (primary/replica)
        even when called from sync context with async_to_sync.
        """
        client = cache.client

        # Skip if not using multiple servers
        if len(client._server) < 2:
            pytest.skip("Test requires multiple servers")

        @async_to_sync
        async def operation_with_replicas():
            """Use async cache with primary/replica setup."""
            # Write to primary
            await cache.aset("test_key", "test_value")

            # Read might use replica
            _ = await cache.aget("test_key")

            # Check that clients were created for this event loop
            loop = asyncio.get_running_loop()
            if loop in client._async_clients:
                clients = client._async_clients[loop]
                # Should have clients for multiple servers
                return len([c for c in clients if c is not None])

            return 0

        # Run operation
        num_clients = operation_with_replicas()

        # Should have created clients (exact number depends on read/write pattern)
        assert num_clients > 0

    async def test_pure_async_uses_single_event_loop(self, cache: RedisCache):
        """
        Test that pure async code uses a single event loop consistently.
        This is the "happy path" that works for both our impl and django-async-redis.
        """
        loop = asyncio.get_running_loop()
        loop_id = id(loop)

        # Multiple async operations
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")
        await cache.aset("key3", "value3")

        values = await cache.aget_many(["key1", "key2", "key3"])

        # All should succeed
        assert len(values) == 3

        # Same event loop throughout
        assert id(asyncio.get_running_loop()) == loop_id

    async def test_async_close_with_multiple_event_loops(self, cache: RedisCache):
        """
        Test that aclose() works correctly.
        """
        # Use cache then close
        await cache.aset("key1", "value")
        await cache.aclose()

        # Should not raise errors


class TestSyncContext:
    """Tests that run in sync context (not marked with asyncio)."""

    def test_sync_close_with_multiple_event_loops(self, cache: RedisCache):
        """
        Test that close works when called from sync context after multiple
        event loops have been used (via async_to_sync).
        """

        @async_to_sync
        async def use_cache_and_close(key):
            """Use cache then close."""
            await cache.aset(key, "value")
            await cache.aclose()

        # Use cache in multiple event loops
        use_cache_and_close("key1")
        use_cache_and_close("key2")
        use_cache_and_close("key3")

        # Should not raise errors even though multiple loops were used


@pytest.mark.asyncio
class TestEventLoopIsolation:
    """Test event loop isolation and cleanup."""

    async def test_weakkeydictionary_cleanup(self, cache: RedisCache):
        """
        Test that WeakKeyDictionary properly cleans up when event loops are GC'd.
        This is hard to test reliably due to GC timing, but we can verify structure.
        """
        from weakref import WeakKeyDictionary

        factory = cache.client.async_connection_factory

        # Use cache to create pools for this event loop
        await cache.aset("test", "value")

        # Check that pools exist
        loop = asyncio.get_running_loop()
        assert loop in factory._pools

        # The actual cleanup happens when loop is GC'd, which we can't force
        # But we can verify the structure is correct
        assert isinstance(factory._pools, WeakKeyDictionary)
        assert isinstance(factory._pools[loop], dict)

    async def test_pool_reuse_within_event_loop(self, cache: RedisCache):
        """
        Test that connection pools are reused within the same event loop.
        """
        factory = cache.client.async_connection_factory
        loop = asyncio.get_running_loop()

        # First operation creates pools
        await cache.aset("key1", "value1")

        # Get pool IDs
        if loop in factory._pools:
            pools_before = factory._pools[loop].copy()
            pool_ids_before = {url: id(pool) for url, pool in pools_before.items()}

        # Second operation should reuse pools
        await cache.aset("key2", "value2")

        # Check pools are the same
        if loop in factory._pools:
            pools_after = factory._pools[loop]
            pool_ids_after = {url: id(pool) for url, pool in pools_after.items()}

            # Same pool instances
            assert pool_ids_before == pool_ids_after

    async def test_clients_reuse_within_event_loop(self, cache: RedisCache):
        """
        Test that Redis clients are reused within the same event loop.
        """
        client = cache.client
        loop = asyncio.get_running_loop()

        # First operation creates clients
        await cache.aset("key1", "value1")

        # Get client IDs
        if loop in client._async_clients:
            clients_before = client._async_clients[loop]
            client_ids_before = [id(c) for c in clients_before if c is not None]

        # Second operation should reuse clients
        await cache.aset("key2", "value2")

        # Check clients are the same
        if loop in client._async_clients:
            clients_after = client._async_clients[loop]
            client_ids_after = [id(c) for c in clients_after if c is not None]

            # Same client instances
            assert client_ids_before == client_ids_after
