# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

try:
    import cPickle as pickle
except ImportError:
    import pickle

import random
import warnings

try:
    from django.utils.encoding import smart_bytes
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes

from django.utils.datastructures import SortedDict
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

try:
    from django.core.cache.backends.base import DEFAULT_TIMEOUT
except ImportError:
    DEFAULT_TIMEOUT = object()

from redis import Redis
from redis.exceptions import ConnectionError, ResponseError
from redis.connection import (Connection,
                              DefaultParser,
                              UnixDomainSocketConnection)

from ..util import CacheKey, load_class, integer_types
from ..exceptions import ConnectionInterrupted
from ..pool import get_or_create_connection_pool


class DefaultClient(object):
    def __init__(self, server, params, backend):
        self._pickle_version = -1
        self._backend = backend
        self._server = server
        self._params = params

        if not self._server:
            raise ImproperlyConfigured("Missing connections string")

        if not isinstance(self._server, (list, tuple, set)):
            self._server = self._server.split(",")

        self._clients = [None] * len(self._server)
        self._options = params.get('OPTIONS', {})

        self.setup_pickle_version()

        self._pool_cls = self._options.get(
            'CONNECTION_POOL_CLASS', 'redis.connection.ConnectionPool')
        self._pool_cls = load_class(self._pool_cls)
        self._pool_cls_kwargs = self._options.get('CONNECTION_POOL_KWARGS', {})

    def __contains__(self, key):
        return self.has_key(key)

    def get_client(self, write=True):
        if write or len(self._server) == 1:
            index = 0
        else:
            index = random.randint(1, len(self._server)-1)

        if self._clients[index] is None:
            self._clients[index] = self.connect(index)

        return self._clients[index]

    @property
    def parser_class(self):
        cls = self._options.get('PARSER_CLASS', None)
        if cls is None:
            return DefaultParser

        return load_class(cls)

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

    def _connect(self, host, port, db):
        """
        Creates a redis connection with connection pool.
        """

        kwargs = {
            "db": db,
            "parser_class": self.parser_class,
            "password": self._options.get('PASSWORD', None),
        }

        if host == "unix":
            kwargs.update({'path': port, 'connection_class': UnixDomainSocketConnection})
        else:
            kwargs.update({'host': host, 'port': port, 'connection_class': Connection})

        if 'SOCKET_TIMEOUT' in self._options:
            kwargs.update({'socket_timeout': int(self._options['SOCKET_TIMEOUT'])})

        kwargs.update(self._pool_cls_kwargs)

        connection_pool = get_or_create_connection_pool(self._pool_cls, **kwargs)
        connection = Redis(connection_pool=connection_pool)
        return connection

    def connect(self, index=0):
        host, port, db = self.parse_connection_string(self._server[index])
        connection = self._connect(host, port, db)
        return connection

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
            client.delete(self.make_key(key, version=version))
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
                client.delete(*keys)
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
            client.delete(*keys)
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

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

    def has_key(self, key, version=None, client=None):
        """
        Test if key exists.
        """

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        try:
            return client.exists(key)
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

    def keys(self, search, client=None):
        if client is None:
            client = self.get_client(write=False)

        pattern = self.make_key(search)
        try:
            encoding_map = [k.decode('utf-8') for k in client.keys(pattern)]
            return [k.split(":", 2)[2] for k in encoding_map]
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

    def make_key(self, key, version=None):
        if isinstance(key, CacheKey):
            return key
        return CacheKey(self._backend.make_key(key, version))

    def close(self, **kwargs):
        if getattr(settings, "DJANGO_REDIS_CLOSE_CONNECTION", False):
            for c in self.client.connection_pool._available_connections:
                c.disconnect()
            del self._client
