import asyncio
import builtins
import random
import re
import socket
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from contextlib import suppress
from typing import (
    Any,
    Optional,
    Union,
    cast,
)
from weakref import WeakKeyDictionary

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache, get_key_func
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.typing import AbsExpiryT, EncodableT, ExpiryT, KeyT, PatternT

from django_redis import pool
from django_redis.client.mixins import SortedSetMixin
from django_redis.exceptions import CompressorError, ConnectionInterrupted
from django_redis.util import CacheKey

_main_exceptions = (
    RedisConnectionError,
    RedisTimeoutError,
    ResponseError,
    socket.timeout,
)

special_re = re.compile("([*?[])")


def glob_escape(s: str) -> str:
    return special_re.sub(r"[\1]", s)


class DefaultClient(SortedSetMixin):
    def __init__(self, server, params: dict[str, Any], backend: BaseCache) -> None:
        self._backend = backend
        self._server = server
        self._params = params

        self.reverse_key = get_key_func(
            params.get("REVERSE_KEY_FUNCTION")
            or "django_redis.util.default_reverse_key",
        )

        if not self._server:
            error_message = "Missing connections string"
            raise ImproperlyConfigured(error_message)

        if not isinstance(self._server, (list, tuple, set)):
            self._server = self._server.split(",")

        self._clients: list[Optional[Redis]] = [None] * len(self._server)
        self._async_clients: WeakKeyDictionary[
            asyncio.AbstractEventLoop,
            Any,
        ] = WeakKeyDictionary()
        self._options = params.get("OPTIONS", {})
        self._replica_read_only = self._options.get("REPLICA_READ_ONLY", True)

        serializer_path = self._options.get(
            "SERIALIZER",
            "django_redis.serializers.pickle.PickleSerializer",
        )
        serializer_cls = import_string(serializer_path)

        compressor_path = self._options.get(
            "COMPRESSOR",
            "django_redis.compressors.identity.IdentityCompressor",
        )
        compressor_cls = import_string(compressor_path)

        self._serializer = serializer_cls(options=self._options)
        self._compressor = compressor_cls(options=self._options)

        self.connection_factory = pool.get_connection_factory(options=self._options)

    def __contains__(self, key: KeyT) -> bool:
        return self.has_key(key)

    def _has_compression_enabled(self) -> bool:
        return (
            self._options.get(
                "COMPRESSOR",
                "django_redis.compressors.identity.IdentityCompressor",
            )
            != "django_redis.compressors.identity.IdentityCompressor"
        )

    def get_next_client_index(
        self,
        write: bool = True,
        tried: Optional[list[int]] = None,
    ) -> int:
        """
        Return a next index for read client. This function implements a default
        behavior for get a next read client for a replication setup.

        Overwrite this function if you want a specific
        behavior.
        """
        if tried is None:
            tried = []

        if tried and len(tried) < len(self._server):
            not_tried = [i for i in range(0, len(self._server)) if i not in tried]
            return random.choice(not_tried)

        if write or len(self._server) == 1:
            return 0

        return random.randint(1, len(self._server) - 1)

    def get_client(
        self,
        write: bool = True,
        tried: Optional[list[int]] = None,
    ) -> Redis:
        """
        Method used for obtain a raw redis client.

        This function is used by almost all cache backend
        operations for obtain a native redis client/connection
        instance.
        """
        index = self.get_next_client_index(write=write, tried=tried)

        if self._clients[index] is None:
            self._clients[index] = self.connect(index)

        return self._clients[index]  # type:ignore

    def get_client_with_index(
        self,
        write: bool = True,
        tried: Optional[list[int]] = None,
    ) -> tuple[Redis, int]:
        """
        Method used for obtain a raw redis client.

        This function is used by almost all cache backend
        operations for obtain a native redis client/connection
        instance.
        """
        index = self.get_next_client_index(write=write, tried=tried)

        if self._clients[index] is None:
            self._clients[index] = self.connect(index)

        return self._clients[index], index  # type:ignore

    async def get_async_client(self, write: bool = True):
        """Get or create async client for current event loop."""
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            msg = "redis.asyncio is required for async support"
            raise ImportError(msg) from e

        loop = asyncio.get_running_loop()

        if loop in self._async_clients:
            return self._async_clients[loop]

        connection_string = self._server[0]
        client = aioredis.from_url(
            connection_string,
            encoding="utf-8",
            decode_responses=False,
        )

        self._async_clients[loop] = client
        return client

    async def aget(
        self,
        key: KeyT,
        default: Optional[Any] = None,
        version: Optional[int] = None,
    ) -> Any:
        """Async get. Returns decoded value if found, default if not."""
        client = await self.get_async_client(write=False)
        key = self.make_key(key, version=version)

        try:
            value = await client.get(key)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        if value is None:
            return default

        return self.decode(value)

    async def aset(
        self,
        key: KeyT,
        value: EncodableT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Async set with optional expiration and nx/xx flags."""
        client = await self.get_async_client(write=True)
        nkey = self.make_key(key, version=version)
        nvalue = self.encode(value)

        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        try:
            if timeout is not None:
                timeout = int(timeout * 1000)

                if timeout <= 0:
                    if nx:
                        return not await self.ahas_key(key, version=version)

                    # redis doesn't support negative timeouts in ex flags
                    # so it seems that it's better to just delete the key
                    # than to set it and than expire in a pipeline
                    return bool(await self.adelete(key, version=version))

            return bool(await client.set(nkey, nvalue, nx=nx, px=timeout, xx=xx))
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def adelete(
        self,
        key: KeyT,
        version: Optional[int] = None,
        prefix: Optional[str] = None,
    ) -> int:
        """Async delete."""
        client = await self.get_async_client(write=True)

        try:
            return await client.delete(
                self.make_key(key, version=version, prefix=prefix),
            )
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def ahas_key(
        self,
        key: KeyT,
        version: Optional[int] = None,
    ) -> bool:
        """Async has_key."""
        client = await self.get_async_client(write=False)
        key = self.make_key(key, version=version)

        try:
            return await client.exists(key) == 1
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def aadd(
        self,
        key: KeyT,
        value: EncodableT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
    ) -> bool:
        """Async add (set if not exists)."""
        return await self.aset(key, value, timeout, version=version, nx=True)

    async def adelete_many(
        self,
        keys: Iterable[KeyT],
        version: Optional[int] = None,
    ) -> int:
        """Async delete_many."""
        client = await self.get_async_client(write=True)
        keys = [self.make_key(k, version=version) for k in keys]

        if not keys:
            return 0

        try:
            return await client.delete(*keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def aclear(self) -> None:
        """Async clear."""
        client = await self.get_async_client(write=True)

        try:
            await client.flushdb()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def aget_many(
        self,
        keys: Iterable[KeyT],
        version: Optional[int] = None,
    ) -> OrderedDict:
        """Async get_many."""
        client = await self.get_async_client(write=False)

        if not keys:
            return OrderedDict()

        recovered_data = OrderedDict()
        map_keys = OrderedDict((self.make_key(k, version=version), k) for k in keys)

        try:
            results = await client.mget(*map_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        for key, value in zip(map_keys, results):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.decode(value)
        return recovered_data

    async def aset_many(
        self,
        data: dict[KeyT, EncodableT],
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
    ) -> None:
        """Async set_many."""
        client = await self.get_async_client(write=True)

        try:
            pipeline = client.pipeline()
            for key, value in data.items():
                nkey = self.make_key(key, version=version)
                nvalue = self.encode(value)

                timeout_val = timeout
                if timeout_val is DEFAULT_TIMEOUT:
                    timeout_val = self._backend.default_timeout

                if timeout_val is not None:
                    timeout_ms = int(timeout_val * 1000)

                    if timeout_ms <= 0:
                        # redis doesn't support negative timeouts in ex flags
                        # so it's better to just delete the key
                        await pipeline.delete(nkey)
                    else:
                        await pipeline.set(nkey, nvalue, px=timeout_ms)
                else:
                    await pipeline.set(nkey, nvalue)

            await pipeline.execute()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    async def atouch(
        self,
        key: KeyT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
    ) -> bool:
        """Async touch."""
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        client = await self.get_async_client(write=True)
        key = self.make_key(key, version=version)

        if timeout is None:
            return bool(await client.persist(key))
        timeout_ms = int(timeout * 1000)
        return bool(await client.pexpire(key, timeout_ms))

    async def attl(
        self,
        key: KeyT,
        version: Optional[int] = None,
    ) -> Optional[int]:
        """Async ttl."""
        client = await self.get_async_client(write=False)
        key_obj = self.make_key(key, version=version)

        if not await client.exists(key_obj):
            return 0

        t = await client.ttl(key_obj)

        if t >= 0:
            return t
        if t == -1:
            return None
        if t == -2:
            return 0
        return None

    async def _aincr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        ignore_key_check: bool = False,
    ) -> int:
        """Internal async incr implementation."""
        client = await self.get_async_client(write=True)
        key_obj = self.make_key(key, version=version)

        try:
            try:
                if not ignore_key_check:
                    lua = """
                    local exists = redis.call('EXISTS', KEYS[1])
                    if (exists == 1) then
                        return redis.call('INCRBY', KEYS[1], ARGV[1])
                    else return false end
                    """
                else:
                    lua = """
                    return redis.call('INCRBY', KEYS[1], ARGV[1])
                    """
                value = await client.eval(lua, 1, key_obj, delta)
                if value is None:
                    error_message = f"Key '{key!r}' not found"
                    raise ValueError(error_message)
            except ResponseError as e:
                timeout = await self.attl(key, version=version)
                if timeout == -2:
                    error_message = f"Key '{key!r}' not found"
                    raise ValueError(error_message) from e
                value = await self.aget(key, version=version) + delta
                await self.aset(key, value, version=version, timeout=timeout)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        return value

    async def aincr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        ignore_key_check: bool = False,
    ) -> int:
        """Async incr."""
        return await self._aincr(
            key=key,
            delta=delta,
            version=version,
            ignore_key_check=ignore_key_check,
        )

    async def adecr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
    ) -> int:
        """Async decr."""
        return await self.aincr(key=key, delta=-delta, version=version)

    async def aclose(self) -> None:
        """Async close."""
        for client in self._async_clients.values():
            await client.aclose()
        self._async_clients.clear()

    def connect(self, index: int = 0) -> Redis:
        """
        Given a connection index, returns a new raw redis client/connection
        instance. Index is used for replication setups and indicates that
        connection string should be used. In normal setups, index is 0.
        """
        return self.connection_factory.connect(self._server[index])

    def disconnect(self, index: int = 0, client: Optional[Redis] = None) -> None:
        """
        delegates the connection factory to disconnect the client
        """
        if client is None:
            client = self._clients[index]

        if client is not None:
            self.connection_factory.disconnect(client)

    def set(
        self,
        key: KeyT,
        value: EncodableT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Persist a value to the cache, and set an optional expiration time.

        Also supports optional nx parameter. If set to True - will use redis
        setnx instead of set.
        """
        nkey = self.make_key(key, version=version)
        nvalue = self.encode(value)

        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        original_client = client
        tried: list[int] = []
        while True:
            try:
                if client is None:
                    client, index = self.get_client_with_index(write=True, tried=tried)

                if timeout is not None:
                    timeout = int(timeout * 1000)

                    if timeout <= 0:
                        if nx:
                            return not self.has_key(key, version=version, client=client)

                        # redis doesn't support negative timeouts in ex flags
                        # so it seems that it's better to just delete the key
                        # than to set it and than expire in a pipeline
                        return bool(self.delete(key, client=client, version=version))

                return bool(client.set(nkey, nvalue, nx=nx, px=timeout, xx=xx))
            except _main_exceptions as e:
                if (
                    not original_client
                    and not self._replica_read_only
                    and len(tried) < len(self._server)
                ):
                    tried.append(index)
                    client = None
                    continue
                raise ConnectionInterrupted(connection=client) from e

    def incr_version(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Adds delta to the cache version for the supplied key. Returns the
        new version.
        """

        if client is None:
            client = self.get_client(write=True)

        if version is None:
            version = self._backend.version

        old_key = self.make_key(key, version)
        value = self.get(old_key, version=version, client=client)

        try:
            ttl = self.ttl(old_key, version=version, client=client)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        if value is None:
            error_message = f"Key '{key!r}' not found"
            raise ValueError(error_message)

        if isinstance(key, CacheKey):
            new_key = self.make_key(key.original_key(), version=version + delta)
        else:
            new_key = self.make_key(key, version=version + delta)

        self.set(new_key, value, timeout=ttl, client=client)
        self.delete(old_key, client=client)
        return version + delta

    def add(
        self,
        key: KeyT,
        value: EncodableT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        return self.set(key, value, timeout, version=version, client=client, nx=True)

    def get(
        self,
        key: KeyT,
        default: Optional[Any] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Any:
        """
        Retrieve a value from the cache.

        Returns decoded value if key is found, the default if not.
        """
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)

        try:
            value = client.get(key)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        if value is None:
            return default

        return self.decode(value)

    def persist(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return client.persist(key)

    def expire(
        self,
        key: KeyT,
        timeout: ExpiryT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout  # type: ignore

        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return client.expire(key, timeout)

    def pexpire(
        self,
        key: KeyT,
        timeout: ExpiryT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout  # type: ignore

        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return bool(client.pexpire(key, timeout))

    def pexpire_at(
        self,
        key: KeyT,
        when: AbsExpiryT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Set an expire flag on a ``key`` to ``when``, which can be represented
        as an integer indicating unix time or a Python datetime object.
        """
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return bool(client.pexpireat(key, when))

    def expire_at(
        self,
        key: KeyT,
        when: AbsExpiryT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Set an expire flag on a ``key`` to ``when``, which can be represented
        as an integer indicating unix time or a Python datetime object.
        """
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return client.expireat(key, when)

    def lock(
        self,
        key: KeyT,
        version: Optional[int] = None,
        timeout: Optional[float] = None,
        sleep: float = 0.1,
        blocking: bool = True,
        blocking_timeout: Optional[float] = None,
        client: Optional[Redis] = None,
        thread_local: bool = True,
    ):
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        return client.lock(
            key,
            timeout=timeout,
            sleep=sleep,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
            thread_local=thread_local,
        )

    def delete(
        self,
        key: KeyT,
        version: Optional[int] = None,
        prefix: Optional[str] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Remove a key from the cache.
        """
        if client is None:
            client = self.get_client(write=True)

        try:
            return client.delete(self.make_key(key, version=version, prefix=prefix))
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def delete_pattern(
        self,
        pattern: str,
        version: Optional[int] = None,
        prefix: Optional[str] = None,
        client: Optional[Redis] = None,
        itersize: Optional[int] = None,
    ) -> int:
        """
        Remove all keys matching pattern.
        """

        if client is None:
            client = self.get_client(write=True)

        pattern = self.make_pattern(pattern, version=version, prefix=prefix)

        try:
            count = 0
            pipeline = client.pipeline()

            for key in client.scan_iter(match=pattern, count=itersize):
                pipeline.delete(key)
                count += 1
            pipeline.execute()

            return count
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def delete_many(
        self,
        keys: Iterable[KeyT],
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Remove multiple keys at once.
        """

        if client is None:
            client = self.get_client(write=True)

        keys = [self.make_key(k, version=version) for k in keys]

        if not keys:
            return 0

        try:
            return client.delete(*keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def clear(self, client: Optional[Redis] = None) -> None:
        """
        Flush all cache keys.
        """

        if client is None:
            client = self.get_client(write=True)

        try:
            client.flushdb()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def decode(self, value: EncodableT) -> Any:
        """
        Decode the given value.
        """
        try:
            value = int(value)
        except (ValueError, TypeError):
            # Handle little values, chosen to be not compressed
            with suppress(CompressorError):
                value = self._compressor.decompress(value)
            value = self._serializer.loads(value)
        return value

    def encode(self, value: EncodableT) -> Union[bytes, int]:
        """
        Encode the given value.
        """

        if isinstance(value, bool) or not isinstance(value, int):
            value = self._serializer.dumps(value)
            return self._compressor.compress(value)

        return value

    def _decode_iterable_result(
        self,
        result: Any,
        covert_to_set: bool = True,
    ) -> Union[list[Any], None, Any]:
        if result is None:
            return None
        if isinstance(result, list):
            if covert_to_set:
                return {self.decode(value) for value in result}
            return [self.decode(value) for value in result]
        return self.decode(result)

    def get_many(
        self,
        keys: Iterable[KeyT],
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> OrderedDict:
        """
        Retrieve many keys.
        """

        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return OrderedDict()

        recovered_data = OrderedDict()

        map_keys = OrderedDict((self.make_key(k, version=version), k) for k in keys)

        try:
            results = client.mget(*map_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        for key, value in zip(map_keys, results):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.decode(value)
        return recovered_data

    def set_many(
        self,
        data: dict[KeyT, EncodableT],
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> None:
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        if client is None:
            client = self.get_client(write=True)

        try:
            pipeline = client.pipeline()
            for key, value in data.items():
                self.set(key, value, timeout, version=version, client=pipeline)
            pipeline.execute()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def _incr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
        ignore_key_check: bool = False,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        try:
            try:
                if not ignore_key_check:
                    lua = """
                    local exists = redis.call('EXISTS', KEYS[1])
                    if (exists == 1) then
                        return redis.call('INCRBY', KEYS[1], ARGV[1])
                    else return false end
                    """
                else:
                    lua = """
                    return redis.call('INCRBY', KEYS[1], ARGV[1])
                    """
                value = client.eval(lua, 1, key, delta)
                if value is None:
                    error_message = f"Key '{key!r}' not found"
                    raise ValueError(error_message)
            except ResponseError as e:
                timeout = self.ttl(key, version=version, client=client)
                if timeout == -2:
                    error_message = f"Key '{key!r}' not found"
                    raise ValueError(error_message) from e
                value = self.get(key, version=version, client=client) + delta
                self.set(key, value, version=version, timeout=timeout, client=client)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        return value

    def incr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
        ignore_key_check: bool = False,
    ) -> int:
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception. if ignore_key_check=True then the key will be
        created and set to the delta value by default.
        """
        return self._incr(
            key=key,
            delta=delta,
            version=version,
            client=client,
            ignore_key_check=ignore_key_check,
        )

    def decr(
        self,
        key: KeyT,
        delta: int = 1,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Decreace delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        return self._incr(key=key, delta=-delta, version=version, client=client)

    def ttl(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[int]:
        """
        Executes TTL redis command and return the "time-to-live" of specified key.
        If key is a non volatile key, it returns None.
        """
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        if not client.exists(key):
            return 0

        t = client.ttl(key)

        if t >= 0:
            return t
        if t == -1:
            return None
        if t == -2:
            return 0
        return None

    def pttl(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[int]:
        """
        Executes PTTL redis command and return the "time-to-live" of specified key.
        If key is a non volatile key, it returns None.
        """
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        if not client.exists(key):
            return 0

        t = client.pttl(key)

        if t >= 0:
            return t
        if t == -1:
            return None
        if t == -2:
            return 0
        return None

    def has_key(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Test if key exists.
        """

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        try:
            return client.exists(key) == 1
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def iter_keys(
        self,
        search: str,
        itersize: Optional[int] = None,
        client: Optional[Redis] = None,
        version: Optional[int] = None,
    ) -> Iterator[str]:
        """
        Same as keys, but uses redis >= 2.8 cursors
        for make memory efficient keys iteration.
        """

        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_pattern(search, version=version)
        for item in client.scan_iter(match=pattern, count=itersize):
            yield self.reverse_key(item.decode())

    def keys(
        self,
        search: str,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> list[Any]:
        """
        Execute KEYS command and return matched results.
        Warning: this can return huge number of results, in
        this case, it strongly recommended use iter_keys
        for it.
        """

        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_pattern(search, version=version)
        try:
            return [self.reverse_key(k.decode()) for k in client.keys(pattern)]
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def make_key(
        self,
        key: KeyT,
        version: Optional[int] = None,
        prefix: Optional[str] = None,
    ) -> KeyT:
        if isinstance(key, CacheKey):
            return key

        if prefix is None:
            prefix = self._backend.key_prefix

        if version is None:
            version = self._backend.version

        return CacheKey(self._backend.key_func(key, prefix, version))

    def make_pattern(
        self,
        pattern: str,
        version: Optional[int] = None,
        prefix: Optional[str] = None,
    ) -> str:
        if isinstance(pattern, CacheKey):
            return pattern

        if prefix is None:
            prefix = self._backend.key_prefix
        prefix = glob_escape(prefix)

        if version is None:
            version = self._backend.version
        version_str = glob_escape(str(version))

        return CacheKey(self._backend.key_func(pattern, prefix, version_str))

    def sadd(
        self,
        key: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.sadd(key, *encoded_values))

    def scard(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return int(client.scard(key))

    def sdiff(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sdiff(*nkeys)}

    def sdiffstore(
        self,
        dest: KeyT,
        *keys: KeyT,
        version_dest: Optional[int] = None,
        version_keys: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version_dest)
        nkeys = [self.make_key(key, version=version_keys) for key in keys]
        return int(client.sdiffstore(dest, *nkeys))

    def sinter(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sinter(*nkeys)}

    def sinterstore(
        self,
        dest: KeyT,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version)
        nkeys = [self.make_key(key, version=version) for key in keys]
        return int(client.sinterstore(dest, *nkeys))

    def smismember(
        self,
        key: KeyT,
        *members,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> list[bool]:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        encoded_members = [self.encode(member) for member in members]

        return [bool(value) for value in client.smismember(key, *encoded_members)]

    def sismember(
        self,
        key: KeyT,
        member: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        member = self.encode(member)
        return bool(client.sismember(key, member))

    def smembers(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return {self.decode(value) for value in client.smembers(key)}

    def smove(
        self,
        source: KeyT,
        destination: KeyT,
        member: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=True)

        source = self.make_key(source, version=version)
        destination = self.make_key(destination)
        member = self.encode(member)
        return bool(client.smove(source, destination, member))

    def spop(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[builtins.set, Any]:
        if client is None:
            client = self.get_client(write=True)

        nkey = self.make_key(key, version=version)
        result = client.spop(nkey, count)
        return self._decode_iterable_result(result)

    def srandmember(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list, Any]:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.srandmember(key, count)
        return self._decode_iterable_result(result, covert_to_set=False)

    def srem(
        self,
        key: KeyT,
        *members: EncodableT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        nmembers = [self.encode(member) for member in members]
        return int(client.srem(key, *nmembers))

    def sscan(
        self,
        key: KeyT,
        match: Optional[str] = None,
        count: Optional[int] = 10,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        if self._has_compression_enabled() and match:
            err_msg = "Using match with compression is not supported."
            raise ValueError(err_msg)

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)

        cursor, result = client.sscan(
            key,
            match=cast("PatternT", self.encode(match)) if match else None,
            count=count,
        )
        return {self.decode(value) for value in result}

    def sscan_iter(
        self,
        key: KeyT,
        match: Optional[str] = None,
        count: Optional[int] = 10,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Iterator[Any]:
        if self._has_compression_enabled() and match:
            err_msg = "Using match with compression is not supported."
            raise ValueError(err_msg)

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        for value in client.sscan_iter(
            key,
            match=cast("PatternT", self.encode(match)) if match else None,
            count=count,
        ):
            yield self.decode(value)

    def sunion(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sunion(*nkeys)}

    def sunionstore(
        self,
        destination: Any,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        destination = self.make_key(destination, version=version)
        encoded_keys = [self.make_key(key, version=version) for key in keys]
        return int(client.sunionstore(destination, *encoded_keys))

    def close(self) -> None:
        close_flag = self._options.get(
            "CLOSE_CONNECTION",
            getattr(settings, "DJANGO_REDIS_CLOSE_CONNECTION", False),
        )
        if close_flag:
            self.do_close_clients()

    def do_close_clients(self) -> None:
        """
        default implementation: Override in custom client
        """
        num_clients = len(self._clients)
        for idx in range(num_clients):
            self.disconnect(index=idx)
        self._clients = [None] * num_clients

    def touch(
        self,
        key: KeyT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Sets a new expiration for a key.
        """

        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        if timeout is None:
            return bool(client.persist(key))
        timeout = int(timeout * 1000)
        return bool(client.pexpire(key, timeout))

    def hset(
        self,
        name: str,
        key: KeyT,
        value: EncodableT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Set the value of hash name at key to value.
        Returns the number of fields added to the hash.
        """
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        nvalue = self.encode(value)
        return int(client.hset(name, nkey, nvalue))

    def hdel(
        self,
        name: str,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Remove keys from hash name.
        Returns the number of fields deleted from the hash.
        """
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        return int(client.hdel(name, nkey))

    def hlen(
        self,
        name: str,
        client: Optional[Redis] = None,
    ) -> int:
        """
        Return the number of items in hash name.
        """
        if client is None:
            client = self.get_client(write=False)
        return int(client.hlen(name))

    def hkeys(
        self,
        name: str,
        client: Optional[Redis] = None,
    ) -> list[Any]:
        """
        Return a list of keys in hash name.
        """
        if client is None:
            client = self.get_client(write=False)
        try:
            return [self.reverse_key(k.decode()) for k in client.hkeys(name)]
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def hexists(
        self,
        name: str,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """
        Return True if key exists in hash name, else False.
        """
        if client is None:
            client = self.get_client(write=False)
        nkey = self.make_key(key, version=version)
        return bool(client.hexists(name, nkey))
