# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

# Import the fastest implementation of
# pickle package. This should be removed
# when python3 come the unique supported
# python version
try:
    import cPickle as pickle
except ImportError:
    import pickle

import random
import warnings

try:
    from django.utils.encoding import smart_bytes
    from django.utils.encoding import smart_text
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes
    from django.utils.encoding import smart_unicode as smart_text

from django.conf import settings
from django.core.cache.backends.base import get_key_func
from django.core.exceptions import ImproperlyConfigured
from django.utils.datastructures import SortedDict

try:
    from django.core.cache.backends.base import DEFAULT_TIMEOUT
except ImportError:
    DEFAULT_TIMEOUT = object()

from redis.exceptions import ConnectionError
from redis.exceptions import ResponseError

# Compatibility with redis-py 2.10.x+

import socket

try:
    from redis.exceptions import TimeoutError
    _main_exceptions = (TimeoutError, ConnectionError, socket.timeout)
except ImportError:
    _main_exceptions = (ConnectionError, socket.timeout)

from redis_cache.util import CacheKey, integer_types
from redis_cache.exceptions import ConnectionInterrupted
from redis_cache import pool

class DefaultClient(object):
    def __init__(self, server, params, backend):
        self._pickle_version = -1
        self._backend = backend
        self._server = server
        self._params = params

        self.reverse_key = get_key_func(params.get('REVERSE_KEY_FUNCTION') or 'redis_cache.util.default_reverse_key')

        if not self._server:
            raise ImproperlyConfigured("Missing connections string")

        if not isinstance(self._server, (list, tuple, set)):
            self._server = self._server.split(",")

        self._clients = [None] * len(self._server)
        self._options = params.get('OPTIONS', {})

        self.setup_pickle_version()
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

    def parse_connection_string(self, constring):
        """
        Method that parse a connection string.
        """
        try:
            host, port, db = constring.split(":")
            port = port if host == "unix" else int(port)
            db = int(db)
            return host, port, db
        except (ValueError, TypeError):
            raise ImproperlyConfigured("Incorrect format '%s'" % (constring))

    def connect(self, index=0):
        """
        Given a connection index, returns a new raw redis client/connection
        instance. Index is used for master/slave setups and indicates that
        connection string should be used. In normal setups, index is 0.
        """
        host, port, db = self.parse_connection_string(self._server[index])
        return self.connection_factory.connect(host, port, db)

    def setup_pickle_version(self):
        if "PICKLE_VERSION" in self._options:
            try:
                self._pickle_version = int(self._options['PICKLE_VERSION'])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, client=None, nx=False):
        """
        Persist a value to the cache, and set an optional expiration time.
        Also supports optional nx parameter. If set to True - will use redis setnx instead of set.
        """

        if not client:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        value = self.pickle(value)

        if timeout is True:
            warnings.warn("Using True as timeout value, is now deprecated.", DeprecationWarning)
            timeout = self._backend.default_timeout

        if timeout == DEFAULT_TIMEOUT:
            timeout = self._backend.default_timeout

        try:
            if nx:
                res = client.setnx(key, value)
                if res and timeout is not None and timeout != 0:
                    return client.expire(key, int(timeout))
                return res
            else:
                if timeout is not None:
                    if timeout > 0:
                        return client.setex(key, value, int(timeout))
                    elif timeout < 0:
                        # redis doesn't support negative timeouts in setex
                        # so it seems that it's better to just delete the key
                        # than to set it and than expire in a pipeline
                        return self.delete(key, client=client)

                return client.set(key, value)
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
        return self.set(key, value, timeout, client=client, nx=True)

    def get(self, key, default=None, version=None, client=None):
        """
        Retrieve a value from the cache.

        Returns unpickled value if key is found, the default if not.
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

        return self.unpickle(value)

    def delete(self, key, version=None, client=None):
        """
        Remove a key from the cache.
        """
        if client is None:
            client = self.get_client(write=True)

        try:
            return client.delete(self.make_key(key, version=version))
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def delete_pattern(self, pattern, version=None, client=None):
        """
        Remove all keys matching pattern.
        """

        if client is None:
            client = self.get_client(write=True)

        pattern = self.make_key(pattern, version=version)
        try:
            keys = client.keys(pattern)

            if keys:
                return client.delete(*keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def delete_many(self, keys, version=None, client=None):
        """
        Remove multiple keys at once.
        """

        if client is None:
            client = self.get_client(write=True)

        if not keys:
            return

        keys = [self.make_key(k, version=version) for k in keys]
        try:
            return client.delete(*keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

    def clear(self, client=None):
        """
        Flush all cache keys.
        """
        if client is None:
            client = self.get_client(write=True)

        client.flushdb()

    @staticmethod
    def unpickle(value):
        """
        Unpickles the given value.
        """
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = smart_bytes(value)
            value = pickle.loads(value)
        return value

    def pickle(self, value):
        """
        Pickle the given value.
        """

        if isinstance(value, bool) or not isinstance(value, integer_types):
            return pickle.dumps(value, self._pickle_version)

        return value

    def get_many(self, keys, version=None, client=None):
        """
        Retrieve many keys.
        """

        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return {}

        recovered_data = SortedDict()

        new_keys = [self.make_key(k, version=version) for k in keys]
        map_keys = dict(zip(new_keys, keys))

        try:
            results = client.mget(*new_keys)
        except _main_exceptions as e:
            raise ConnectionInterrupted(connection=client, parent=e)

        for key, value in zip(new_keys, results):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.unpickle(value)
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
                # elif int is pickled. so redis sees the data as string.
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
        return client.ttl(key)

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
        cursor = b"0"

        while True:
            cursor, data = client.scan(cursor, match=pattern, count=itersize)

            for item in data:
                item = smart_text(item)
                yield self.reverse_key(item)

            if cursor == b"0":
                break

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

    def make_key(self, key, version=None):
        if isinstance(key, CacheKey):
            return key
        return CacheKey(self._backend.make_key(key, version))

    def close(self, **kwargs):
        if getattr(settings, "DJANGO_REDIS_CLOSE_CONNECTION", False):
            for c in self.client.connection_pool._available_connections:
                c.disconnect()
            del self._client
