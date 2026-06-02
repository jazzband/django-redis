from __future__ import annotations

import random
import re
import socket
import sys
from contextlib import suppress
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    TypeAlias,
    cast,
    overload,
)

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache, get_key_func
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    ResponseError,
    TimeoutError as RedisTimeoutError,
)

from django_redis.client.mixins import SortedSetMixin
from django_redis.exceptions import CompressorError, ConnectionInterrupted
from django_redis.pool import (
    ConnectionFactoryProtocol,
    ConnectionPoolType,
    RedisParserType,
    RedisType,
    get_connection_factory,
)
from django_redis.util import CacheKey

if sys.version_info < (3, 13):
    from typing_extensions import TypeVar
else:
    from typing import TypeVar

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping

    from redis import Redis
    from redis.lock import Lock
    from redis.typing import AbsExpiryT, ExpiryT, FieldT, PatternT

    from django_redis.compressors.base import BaseCompressor
    from django_redis.compressors.identity import IdentityCompressor
    from django_redis.serializers.base import BaseSerializer
    from django_redis.serializers.pickle import PickleSerializer

    Set: TypeAlias = set

CompressorType = TypeVar(
    "CompressorType",
    bound="BaseCompressor",
    default="IdentityCompressor",
)
SerializerType = TypeVar(
    "SerializerType",
    bound="BaseSerializer",
    default="PickleSerializer",
)

_main_exceptions = (
    RedisConnectionError,
    RedisTimeoutError,
    ResponseError,
    socket.timeout,
)

special_re = re.compile("([*?[])")


def glob_escape(s: str) -> str:
    return special_re.sub(r"[\1]", s)


class DefaultClient(
    SortedSetMixin,
    Generic[
        RedisType,
        ConnectionPoolType,
        RedisParserType,
        SerializerType,
        CompressorType,
    ],
):
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

        self._clients: list[RedisType | None] = [None] * len(self._server)
        self._options = params.get("OPTIONS", {})
        self._replica_read_only = self._options.get("REPLICA_READ_ONLY", True)

        serializer_path = self._options.get(
            "SERIALIZER",
            "django_redis.serializers.pickle.PickleSerializer",
        )
        serializer_cls: type[SerializerType] = import_string(serializer_path)

        compressor_path = self._options.get(
            "COMPRESSOR",
            "django_redis.compressors.identity.IdentityCompressor",
        )
        compressor_cls: type[CompressorType] = import_string(compressor_path)

        self._serializer = serializer_cls(options=self._options)
        self._compressor = compressor_cls(options=self._options)

        self.connection_factory: ConnectionFactoryProtocol[
            RedisType,
            ConnectionPoolType,
            RedisParserType,
        ] = get_connection_factory(self._options)

    def __contains__(self, key: str) -> bool:
        return self.has_key(key)

    def _has_compression_enabled(self) -> bool:
        return (
            cast(
                "str",
                self._options.get(
                    "COMPRESSOR",
                    "django_redis.compressors.identity.IdentityCompressor",
                ),
            )
            != "django_redis.compressors.identity.IdentityCompressor"
        )

    def get_next_client_index(
        self,
        write: bool = True,
        tried: list[int] | None = None,
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
        tried: list[int] | None = None,
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
        tried: list[int] | None = None,
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

    def connect(self, index: int = 0) -> RedisType:
        """
        Given a connection index, returns a new raw redis client/connection
        instance. Index is used for replication setups and indicates that
        connection string should be used. In normal setups, index is 0.
        """
        return self.connection_factory.connect(self._server[index])

    def disconnect(self, index: int = 0, client: RedisType | None = None) -> None:
        """
        delegates the connection factory to disconnect the client
        """
        if client is None:
            client = self._clients[index]

        if client is not None:
            self.connection_factory.disconnect(client)

    def set(
        self,
        key: str,
        value: Any,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
        client: Redis | None = None,
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
                    # Convert to milliseconds
                    timeout = int(timeout * 1000)

                    if timeout <= 0:
                        if nx:
                            # Using negative timeouts when nx is True should
                            # not expire (in our case delete) the value if it exists.
                            # Obviously expire not existent value is noop.
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
        key: str,
        delta: int = 1,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        value: Any,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        return self.set(key, value, timeout, version=version, client=client, nx=True)

    def get(
        self,
        key: str,
        default: Any | None = None,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return client.persist(key)

    def expire(
        self,
        key: str,
        timeout: ExpiryT,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout  # type: ignore

        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return client.expire(key, timeout)

    def pexpire(
        self,
        key: str,
        timeout: ExpiryT,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout  # type: ignore

        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        return bool(client.pexpire(key, timeout))

    def pexpire_at(
        self,
        key: str,
        when: AbsExpiryT,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        when: AbsExpiryT,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        version: int | None = None,
        timeout: float | None = None,
        sleep: float = 0.1,
        blocking: bool = True,
        blocking_timeout: float | None = None,
        client: Redis | None = None,
        thread_local: bool = True,
    ) -> Lock:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        return cast(
            "Lock",
            client.lock(
                key,
                timeout=timeout,
                sleep=sleep,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
                thread_local=thread_local,
            ),
        )

    def delete(
        self,
        key: str,
        version: int | None = None,
        prefix: str | None = None,
        client: Redis | None = None,
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
        version: int | None = None,
        prefix: str | None = None,
        client: Redis | None = None,
        itersize: int | None = None,
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
        keys: Iterable[str],
        version: int | None = None,
        client: Redis | None = None,
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

    def clear(self, client: Redis | None = None) -> None:
        """
        Flush all cache keys.
        """

        if client is None:
            client = self.get_client(write=True)

        try:
            client.flushdb()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def decode(self, value: bytes | int | str) -> Any:
        """
        Decode the given value.
        """
        try:
            value = int(value)
        except (ValueError, TypeError):
            # str should not happen, but fail in the compressor/serializer
            value = cast("bytes", value)

            # Handle little values, chosen to be not compressed
            with suppress(CompressorError):
                value = self._compressor.decompress(value)
            value = self._serializer.loads(value)
        return value

    @overload
    def encode(self, value: Any, *, allow_int: Literal[False]) -> bytes: ...
    @overload
    def encode(self, value: Any, *, allow_int: bool = ...) -> bytes | int: ...
    def encode(self, value: Any, *, allow_int: bool = True) -> bytes | int:
        """
        Encode the given value.
        """

        if (
            isinstance(value, (bool, Enum))
            or not allow_int
            or not isinstance(value, int)
        ):
            value = self._serializer.dumps(value)
            return self._compressor.compress(value)

        return value

    def _decode_iterable_result(
        self,
        result: Any,
        covert_to_set: bool = True,
    ) -> list[Any] | None | Any:
        if result is None:
            return None
        if isinstance(result, list):
            if covert_to_set:
                return {self.decode(value) for value in result}
            return [self.decode(value) for value in result]
        return self.decode(result)

    def get_many(
        self,
        keys: Collection[str],
        version: int | None = None,
        client: Redis | None = None,
    ) -> dict:
        """
        Retrieve many keys.
        """

        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return {}

        recovered_data = {}

        map_keys = {self.make_key(k, version=version): k for k in keys}

        try:
            results = client.mget(*map_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        for key, value in zip(map_keys, results, strict=True):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.decode(value)
        return recovered_data

    def set_many(
        self,
        data: dict[str, Any],
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        delta: int = 1,
        version: int | None = None,
        client: Redis | None = None,
        ignore_key_check: bool = False,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        try:
            try:
                # if key expired after exists check, then we get
                # key with wrong value and ttl -1.
                # use lua script for atomicity
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
                value: int | Literal[False] | None = client.eval(lua, 1, key, delta)
                if value is None or value is False:
                    error_message = f"Key '{key!r}' not found"
                    raise ValueError(error_message)
            except ResponseError as e:
                # if cached value or total value is greater than 64 bit signed
                # integer.
                # elif int is encoded. so redis sees the data as string.
                # In this situations redis will throw ResponseError

                # try to keep TTL of key
                timeout = self.ttl(key, version=version, client=client)

                # returns -2 if the key does not exist
                # means, that key have expired
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
        key: str,
        delta: int = 1,
        version: int | None = None,
        client: Redis | None = None,
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
        key: str,
        delta: int = 1,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """
        Decreace delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        return self._incr(key=key, delta=-delta, version=version, client=client)

    def ttl(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int | None:
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

        # Should never reach here
        return None

    def pttl(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int | None:
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

        # Should never reach here
        return None

    def has_key(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
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
        itersize: int | None = None,
        client: Redis | None = None,
        version: int | None = None,
    ) -> Iterator[str]:
        """
        Same as keys, but uses redis >= 2.8 cursors
        for make memory efficient keys iteration.
        """

        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_pattern(search, version=version)
        for item in client.scan_iter(match=pattern, count=itersize):
            yield self.reverse_key(item.decode() if isinstance(item, bytes) else item)

    def keys(
        self,
        search: str,
        version: int | None = None,
        client: Redis | None = None,
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
            return [
                self.reverse_key(k.decode() if isinstance(k, bytes) else k)
                for k in client.keys(pattern)
            ]
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def make_key(
        self,
        key: str,
        version: int | None = None,
        prefix: str | None = None,
    ) -> CacheKey:
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
        version: int | None = None,
        prefix: str | None = None,
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
        key: str,
        *values: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.sadd(key, *encoded_values))

    def scard(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return int(client.scard(key))

    def sdiff(
        self,
        *keys: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sdiff(*nkeys)}  # type: ignore[arg-type]

    def sdiffstore(
        self,
        dest: str,
        *keys: str,
        version_dest: int | None = None,
        version_keys: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version_dest)
        nkeys = [self.make_key(key, version=version_keys) for key in keys]
        return int(client.sdiffstore(dest, *nkeys))  # type: ignore[arg-type]

    def sinter(
        self,
        *keys: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sinter(*nkeys)}  # type: ignore[arg-type]

    def sinterstore(
        self,
        dest: str,
        *keys: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version)
        nkeys = [self.make_key(key, version=version) for key in keys]
        return int(client.sinterstore(dest, *nkeys))  # type: ignore[arg-type]

    def smismember(
        self,
        key: str,
        *members,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[bool]:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        encoded_members = [self.encode(member) for member in members]

        return [bool(value) for value in client.smismember(key, *encoded_members)]  # type: ignore[arg-type]

    def sismember(
        self,
        key: str,
        member: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        member = self.encode(member)
        return bool(client.sismember(key, member))

    def smembers(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set[Any]:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return {self.decode(value) for value in client.smembers(key)}

    def smove(
        self,
        source: str,
        destination: str,
        member: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        if client is None:
            client = self.get_client(write=True)

        source = self.make_key(source, version=version)
        destination = self.make_key(destination)
        member = self.encode(member)
        return bool(client.smove(source, destination, member))

    def spop(
        self,
        key: str,
        count: int | None = None,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set | Any:
        if client is None:
            client = self.get_client(write=True)

        nkey = self.make_key(key, version=version)
        result = client.spop(nkey, count)
        return self._decode_iterable_result(result)

    def srandmember(
        self,
        key: str,
        count: int | None = None,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list | Any:
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.srandmember(key, count)
        return self._decode_iterable_result(result, covert_to_set=False)

    def srem(
        self,
        key: str,
        *members: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        nmembers = [self.encode(member) for member in members]
        return int(client.srem(key, *nmembers))

    def sscan(
        self,
        key: str,
        match: str | None = None,
        count: int | None = 10,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set[Any]:
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
        key: str,
        match: str | None = None,
        count: int | None = 10,
        version: int | None = None,
        client: Redis | None = None,
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
        *keys: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> Set[Any]:
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sunion(*nkeys)}  # type: ignore[arg-type]

    def sunionstore(
        self,
        destination: Any,
        *keys: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        if client is None:
            client = self.get_client(write=True)

        destination = self.make_key(destination, version=version)
        encoded_keys = [self.make_key(key, version=version) for key in keys]
        return int(client.sunionstore(destination, *encoded_keys))  # type: ignore[arg-type]

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
        key: str,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
        client: Redis | None = None,
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

        # Convert to milliseconds
        timeout = int(timeout * 1000)
        return bool(client.pexpire(key, timeout))

    def hset(
        self,
        key: str,
        field: FieldT | None = None,
        value: Any | None = None,
        mapping: Mapping[FieldT, Any] | None = None,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """
        Set the value of hash key at field to value.
        Returns the number of fields added to the hash.
        """
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        return int(
            client.hset(
                nkey,
                key=field,
                value=self.encode(value) if value is not None else None,
                mapping={f: self.encode(v) for f, v in mapping.items()}
                if mapping is not None
                else None,
            ),
        )

    def hdel(
        self,
        key: str,
        field: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """
        Remove fields from hash key.
        Returns the number of fields deleted from the hash.
        """
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        return int(client.hdel(nkey, field))

    def hlen(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """
        Return the number of items in hash key.
        """
        if client is None:
            client = self.get_client(write=False)
        nkey = self.make_key(key, version=version)
        return int(client.hlen(nkey))

    def hkeys(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[str]:
        """
        Return a list of fields in hash key.
        """
        if client is None:
            client = self.get_client(write=False)
        nkey = self.make_key(key, version=version)
        try:
            return [
                k.decode() if isinstance(k, bytes) else k for k in client.hkeys(nkey)
            ]
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def hexists(
        self,
        key: str,
        field: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> bool:
        """
        Return True if field exists in hash key, else False.
        """
        if client is None:
            client = self.get_client(write=False)
        nkey = self.make_key(key, version=version)
        return bool(client.hexists(nkey, field))
