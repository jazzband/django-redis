# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import random
import socket
import warnings
import zlib
from collections import OrderedDict

try:
    from django.utils.encoding import smart_text
except ImportError:
    from django.utils.encoding import smart_unicode as smart_text

from django.conf import settings
from django.core.cache.backends.base import get_key_func
from django.core.exceptions import ImproperlyConfigured

try:
    from django.core.cache.backends.base import DEFAULT_TIMEOUT
except ImportError:
    DEFAULT_TIMEOUT = object()

from redis.exceptions import ConnectionError
from redis.exceptions import ResponseError

# Compatibility with redis-py 2.10.x+

try:
    from redis.exceptions import TimeoutError, ResponseError
    _main_exceptions = (TimeoutError, ResponseError, ConnectionError, socket.timeout)
except ImportError:
    _main_exceptions = (ConnectionError, socket.timeout)

from ..util import CacheKey, load_class, integer_types
from ..exceptions import ConnectionInterrupted, CompressorError
from .. import pool


class DefaultClient(object):
    def __init__(self, server, params, backend):
        self._backend = backend
        self._server = server
        self._params = params

        self.reverse_key = get_key_func(params.get("REVERSE_KEY_FUNCTION") or
                                        "django_redis.util.default_reverse_key")

        if not self._server:
            raise ImproperlyConfigured("Missing connections string")

        if not isinstance(self._server, (list, tuple, set)):
            self._server = self._server.split(",")

        self._clients = [None] * len(self._server)
        self._options = params.get("OPTIONS", {})

        serializer_path = self._options.get("SERIALIZER", "django_redis.serializers.pickle.PickleSerializer")
        serializer_cls = load_class(serializer_path)

        compressor_path = self._options.get("COMPRESSOR", "django_redis.compressors.identity.IdentityCompressor")
        compressor_cls = load_class(compressor_path)

        self._serializer = serializer_cls(options=self._options)
        self._compressor = compressor_cls(options=self._options);

        self.connection_factory = pool.get_connection_factory(options=self._options)

    def __contains__(self, key):
        return self.has_key(key)

    def get_next_client_index(self, write=True):
        """
        Return a next index for read client.
        This function implements a default behavior for
        get a next read client for master-slave setup.

        Overwrite this function if you want a specific
        behavior.
        """
        if write or len(self._server) == 1:
            return 0

        return random.randint(1, len(self._server) - 1)

    def get_client(self, write=True):
        """
        Method used for obtain a raw redis client.

        This function is used by almost all cache backend
        operations for obtain a native redis client/connection
        instance.
        """
        index = self.get_next_client_index(write=write)

        if self._clients[index] is None:
            self._clients[index] = self.connect(index)

        return self._clients[index]

    def connect(self, index=0):
        """
        Given a connection index, returns a new raw redis client/connection
        instance. Index is used for master/slave setups and indicates that
        connection string should be used. In normal setups, index is 0.
        """
        return self.connection_factory.connect(self._server[index])

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, client=None, nx=False, xx=False):
        """
        Persist a value to the cache, and set an optional expiration time.
        Also supports optional nx parameter. If set to True - will use redis setnx instead of set.
        """

        if not client:
            client = self.get_client(write=True)

        nkey = self.make_key(key, version=version)
        nvalue = self.encode(value)

        if timeout is True:
            warnings.warn("Using True as timeout value, is now deprecated.", DeprecationWarning)
            timeout = self._backend.default_timeout

        if timeout == DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        try:
            if timeout is not None:
                if timeout > 0:
                    # If "timeout" is 0.1, this would make it 0, which redis
                    # considers as "don't expire". Instead, set it to a minimum
                    # of 1.
                    timeout = max(1, int(timeout))
                elif timeout <= 0:
                    if nx:
                        # Using negative timeouts when nx is True should
                        # not expire (in our case delete) the value if it exists.
                        # Obviously expire not existent value is noop.
                        timeout = None
                    else:
                        # redis doesn't support negative timeouts in ex flags
                        # so it seems that it's better to just delete the key
                        # than to set it and than expire in a pipeline
                        return self.delete(key, client=client, version=version)

            return client.set(nkey, nvalue, nx=nx, ex=timeout, xx=xx)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def incr_version(self, key, delta=1, version=None, client=None):
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
            ttl = client.ttl(old_key)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

        if value is None:
            raise ValueError("Key '%s' not found" % key)

        if isinstance(key, CacheKey):
            new_key = self.make_key(key.original_key(), version=version + delta)
        else:
            new_key = self.make_key(key, version=version + delta)

        self.set(new_key, value, timeout=ttl, client=client)
        self.delete(old_key, client=client)
        return version + delta

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, client=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        return self.set(key, value, timeout, version=version, client=client, nx=True)

    def get(self, key, default=None, version=None, client=None):
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
            raise ConnectionInterrupted(connection=client, parent=e)

        if value is None:
            return default

        return self.decode(value)

    def persist(self, key, version=None, client=None):
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        if client.exists(key):
            client.persist(key)

    def expire(self, key, timeout, version=None, client=None):
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        if client.exists(key):
            client.expire(key, timeout)

    def lock(self, key, version=None, timeout=None, sleep=0.1,
             blocking_timeout=None, client=None):
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        return client.lock(key, timeout=timeout, sleep=sleep,
                           blocking_timeout=blocking_timeout)

    def delete(self, key, version=None, prefix=None, client=None):
        """
        Remove a key from the cache.
        """
        if client is None:
            client = self.get_client(write=True)

        try:
            return client.delete(self.make_key(key, version=version,
                                               prefix=prefix))
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def delete_pattern(self, pattern, version=None, prefix=None, client=None):
        """
        Remove all keys matching pattern.
        """

        if client is None:
            client = self.get_client(write=True)

        pattern = self.make_key(pattern, version=version, prefix=prefix)
        try:
            count = 0
            for key in client.scan_iter(pattern):
                client.delete(key)
                count += 1
            return count
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def delete_many(self, keys, version=None, client=None):
        """
        Remove multiple keys at once.
        """

        if client is None:
            client = self.get_client(write=True)

        keys = [self.make_key(k, version=version) for k in keys]

        if not keys:
            return

        try:
            return client.delete(*keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def clear(self, client=None):
        """
        Flush all cache keys.
        """
        self.delete_pattern("*", client=client)

    def decode(self, value):
        """
        Decode the given value.
        """
        try:
            value = int(value)
        except (ValueError, TypeError):
            try:
                value = self._compressor.decompress(value)
            except CompressorError:
                # Handle little values, chosen to be not compressed
                pass
            value = self._serializer.loads(value)
        return value

    def encode(self, value):
        """
        Encode the given value.
        """

        if isinstance(value, bool) or not isinstance(value, integer_types):
            value = self._serializer.dumps(value)
            value = self._compressor.compress(value)
            return value

        return value

    def get_many(self, keys, version=None, client=None):
        """
        Retrieve many keys.
        """

        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return {}

        recovered_data = OrderedDict()

        new_keys = [self.make_key(k, version=version) for k in keys]
        map_keys = dict(zip(new_keys, keys))

        try:
            results = client.mget(*new_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

        for key, value in zip(new_keys, results):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.decode(value)
        return recovered_data

    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None, client=None):
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
            raise ConnectionInterrupted(connection=client, parent=e)

    def _incr(self, key, delta=1, version=None, client=None):
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)

        try:
            if not client.exists(key):
                raise ValueError("Key '%s' not found" % key)

            try:
                value = client.incr(key, delta)
            except ResponseError:
                # if cached value or total value is greater than 64 bit signed
                # integer.
                # elif int is encoded. so redis sees the data as string.
                # In this situations redis will throw ResponseError

                # try to keep TTL of key
                timeout = client.ttl(key)
                value = self.get(key, version=version, client=client) + delta
                self.set(key, value, version=version, timeout=timeout,
                         client=client)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

        return value

    def incr(self, key, delta=1, version=None, client=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        return self._incr(key=key, delta=delta, version=version, client=client)

    def decr(self, key, delta=1, version=None, client=None):
        """
        Decreace delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        return self._incr(key=key, delta=-delta, version=version,
                          client=client)

    def ttl(self, key, version=None, client=None):
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
        elif t == -1:
            return None
        elif t == -2:
            return 0
        else:
            # Should never reach here
            return None

    def has_key(self, key, version=None, client=None):
        """
        Test if key exists.
        """

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        try:
            return client.exists(key)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def iter_keys(self, search, itersize=None, client=None, version=None):
        """
        Same as keys, but uses redis >= 2.8 cursors
        for make memory efficient keys iteration.
        """

        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_key(search, version=version)
        for item in client.scan_iter(match=pattern, count=itersize):
            item = smart_text(item)
            yield self.reverse_key(item)

    def keys(self, search, version=None, client=None):
        """
        Execute KEYS command and return matched results.
        Warning: this can return huge number of results, in
        this case, it strongly recommended use iter_keys
        for it.
        """

        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_key(search, version=version)
        try:
            encoding_map = [smart_text(k) for k in client.keys(pattern)]
            return [self.reverse_key(k) for k in encoding_map]
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def make_key(self, key, version=None, prefix=None):
        if isinstance(key, CacheKey):
            return key

        if prefix is None:
            prefix = self._backend.key_prefix

        if version is None:
            version = self._backend.version

        return CacheKey(self._backend.key_func(key, prefix, version))

    def close(self, **kwargs):
        if getattr(settings, "DJANGO_REDIS_CLOSE_CONNECTION", False):
            for c in self.client.connection_pool._available_connections:
                c.disconnect()
            del self._client
