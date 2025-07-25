import random
import socket
import time
from collections import OrderedDict

from django.conf import settings
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from django_redis.client.default import DEFAULT_TIMEOUT, DefaultClient
from django_redis.exceptions import ConnectionInterrupted

_main_exceptions = (
    RedisConnectionError,
    RedisTimeoutError,
    ResponseError,
    socket.timeout,
)


class Marker:
    """
    Dummy class for use as
    marker for herded keys.
    """

    pass


def _is_expired(x, herd_timeout: int) -> bool:
    if x >= herd_timeout:
        return True
    val = x + random.randint(1, herd_timeout)

    return val >= herd_timeout


class HerdClient(DefaultClient):
    def __init__(self, *args, **kwargs):
        self._marker = Marker()
        self._herd_timeout = getattr(settings, "CACHE_HERD_TIMEOUT", 60)
        super().__init__(*args, **kwargs)

    def _pack(self, value, timeout):
        herd_timeout = (timeout or self._backend.default_timeout) + int(time.time())
        return self._marker, value, herd_timeout

    def _unpack(self, value):
        try:
            marker, unpacked, herd_timeout = value
        except (ValueError, TypeError):
            return value, False

        if not isinstance(marker, Marker):
            return value, False

        now = int(time.time())
        if herd_timeout < now:
            x = now - herd_timeout
            return unpacked, _is_expired(x, self._herd_timeout)

        return unpacked, False

    def set(
        self,
        key,
        value,
        timeout=DEFAULT_TIMEOUT,
        version=None,
        client=None,
        nx=False,
        xx=False,
    ):
        if timeout is DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        if timeout is None or timeout <= 0:
            return super().set(
                key,
                value,
                timeout=timeout,
                version=version,
                client=client,
                nx=nx,
                xx=xx,
            )

        packed = self._pack(value, timeout)
        real_timeout = timeout + self._herd_timeout

        return super().set(
            key,
            packed,
            timeout=real_timeout,
            version=version,
            client=client,
            nx=nx,
        )

    def get(self, key, default=None, version=None, client=None):
        packed = super().get(key, default=default, version=version, client=client)
        val, refresh = self._unpack(packed)

        if refresh:
            return default

        return val

    def get_many(self, keys, version=None, client=None):
        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return {}

        recovered_data = OrderedDict()

        new_keys = [self.make_key(key, version=version) for key in keys]
        map_keys = dict(zip(new_keys, keys))

        try:
            results = client.mget(*new_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

        for key, value in zip(new_keys, results):
            if value is None:
                continue

            val, refresh = self._unpack(self.decode(value))
            recovered_data[map_keys[key]] = None if refresh else val

        return recovered_data

    def set_many(
        self,
        data,
        timeout=DEFAULT_TIMEOUT,
        version=None,
        client=None,
        herd=True,
    ):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        if client is None:
            client = self.get_client(write=True)

        set_function = self.set if herd else super().set

        try:
            pipeline = client.pipeline()
            for key, value in data.items():
                set_function(key, value, timeout, version=version, client=pipeline)
            pipeline.execute()
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client) from e

    def incr(self, *args, **kwargs):
        raise NotImplementedError

    def decr(self, *args, **kwargs):
        raise NotImplementedError

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None, client=None):
        if client is None:
            client = self.get_client(write=True)

        value = self.get(key, version=version, client=client)
        if value is None:
            return False

        self.set(key, value, timeout=timeout, version=version, client=client)
        return True
