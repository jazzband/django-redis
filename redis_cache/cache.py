# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import smart_unicode, smart_str
from django.utils.datastructures import SortedDict
from django.utils import importlib

try:
    import cPickle as pickle
except ImportError:
    import pickle

from collections import defaultdict

from redis import Redis
from redis.connection import DefaultParser
from .util import CacheKey, ConnectionPoolHandler

import re

class RedisCache(BaseCache):
    _pickle_version = -1

    def __init__(self, server, params):
        """
        Connect to Redis, and set up cache backend.
        """
        self._init(server, params)
        super(RedisCache, self).__init__(params)

    def _connect(self):
        unix_socket_path = None
        if ':' in self._server:
            host, port = self._server.split(':')
            try:
                port = int(port)
            except (ValueError, TypeError):
                raise ImproperlyConfigured("port value must be an integer")

        else:
            host, port = None, None
            unix_socket_path = self._server

        # parse database
        _db = self._params.get('db', self._options.get('DB', 1))
        try:
            _db = int(_db)
        except (ValueError, TypeError):
            raise ImproperlyConfigured("db value must be an integer")

        # params for connection pool.
        kwargs = {
            'db': _db,
            'password': self.password,
            'host': host,
            'port': port,
            'unix_socket_path': unix_socket_path,
        }

        connection_pool = ConnectionPoolHandler()\
            .connection_pool(parser_class=self.parser_class, **kwargs)
        self._client = Redis(connection_pool=connection_pool)

    def _init(self, server, params):
        super(RedisCache, self).__init__(params)
        self._server = server
        self._params = params
        self._options = params.get('OPTIONS', {})

        if "PICKLE_VERSION" in self._options:
            try:
                self._pickle_version = int(self._options['PICKLE_VERSION'])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

        self._connect()

    def make_key(self, key, version=None):
        if not isinstance(key, CacheKey):
            key = CacheKey(super(RedisCache, self).make_key(key, version))
        return key

    def incr_version(self, key, delta=1, version=None, client=None):
        """
        Adds delta to the cache version for the supplied key. Returns the
        new version.
        """
        if client is None:
            client = self._client

        if version is None:
            version = self.version

        old_key = self.make_key(key, version)
        value = self.get(old_key, version=version, client=client)
        ttl = client.ttl(old_key)

        if value is None:
            raise ValueError("Key '%s' not found" % key)

        if isinstance(key, CacheKey):
            new_key = self.make_key(key.original_key(), version=version+delta)
        else:
            new_key = self.make_key(key, version=version+delta)

        self.set(new_key, value, timeout=ttl)
        self.delete(old_key, client=client)
        return version + delta

    @property
    def password(self):
        return self._options.get('PASSWORD', None)

    @property
    def parser_class(self):
        cls = self._options.get('PARSER_CLASS', None)
        if cls is None:
            return DefaultParser

        mod_path, cls_name = cls.rsplit('.', 1)
        try:
            mod = importlib.import_module(mod_path)
            parser_class = getattr(mod, cls_name)
        except (AttributeError, ImportError):
            raise ImproperlyConfigured("Could not find parser class '%s'" % parser_class)
        except ImportError as e:
            raise ImproperlyConfigured("Could not find module '%s'" % e)
        return parser_class

    def __getstate__(self):
        return {'params': self._params, 'server': self._server}

    def __setstate__(self, state):
        self._init(**state)

    def close(self, **kwargs):
        for c in self._client.connection_pool._available_connections:
            c.disconnect()

    def add(self, key, value, timeout=None, version=None, client=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """

        if client is None:
            client = self._client

        key = self.make_key(key, version=version)

        if client.exists(key):
            return False

        return self.set(key, value, timeout, client=client)

    def get(self, key, default=None, version=None, client=None):
        """
        Retrieve a value from the cache.

        Returns unpickled value if key is found, the default if not.
        """
        if client is None:
            client = self._client

        key = self.make_key(key, version=version)
        value = client.get(key)

        if value is None:
            return default

        return self.unpickle(value)

    def _set(self, key, value, timeout, client):
        if timeout == 0:
            return client.set(key, value)
        elif timeout > 0:
            return client.setex(key, value, int(timeout))
        else:
            return False

    def set(self, key, value, timeout=None, version=None, client=None):
        """
        Persist a value to the cache, and set an optional expiration time.
        """

        if not client:
            client = self._client

        key = self.make_key(key, version=version)
        if timeout is None:
            timeout = self.default_timeout

        result = self._set(key, self.pickle(value), int(timeout), client)
        return result

    def delete(self, key, version=None, client=None):
        """
        Remove a key from the cache.
        """
        if client is None:
            client = self._client

        client.delete(self.make_key(key, version=version))

    def delete_pattern(self, pattern, version=None, client=None):
        """
        Remove all keys matching pattern.
        """

        if client is None:
            client = self._client

        pattern = self.make_key(pattern, version=version)
        keys = client.keys(pattern)
        client.delete(*keys)

    def delete_many(self, keys, version=None):
        """
        Remove multiple keys at once.
        """
        if keys:
            keys = map(lambda key: self.make_key(key, version=version), keys)
            self._client.delete(*keys)

    def clear(self):
        """
        Flush all cache keys.
        """
        self._client.flushdb()

    def unpickle(self, value):
        """
        Unpickles the given value.
        """
        value = smart_str(value)
        return pickle.loads(value)

    def pickle(self, value):
        """
        Pickle the given value.
        """
        return pickle.dumps(value, self._pickle_version)

    def get_many(self, keys, version=None):
        """
        Retrieve many keys.
        """
        if not keys:
            return {}
        recovered_data = SortedDict()

        new_keys = map(lambda key: self.make_key(key, version=version), keys)
        map_keys = dict(zip(new_keys, keys))

        results = self._client.mget(new_keys)
        for key, value in zip(new_keys, results):
            if value is None:
                continue

            recovered_data[map_keys[key]] = self.unpickle(value)
        return recovered_data

    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        pipeline = self._client.pipeline()
        for key, value in data.iteritems():
            self.set(key, value, timeout, version=version, client=pipeline)
        pipeline.execute()

    def incr(self, key, delta=1, version=None, client=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """

        if client is None:
            client = self._client

        key = self.make_key(key, version=version)
        exists = client.exists(key)

        if not client.exists(key):
            raise ValueError("Key '%s' not found" % key)

        value = self.get(key, version=version, client=client) + delta
        self.set(key, value, version=version, client=client)
        return value

    def decr(self, key, delta=1, version=None, client=None):
        """
        Decreace delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        if client is None:
            client = self._client

        key = self.make_key(key, version=version)

        if not client.exists(key):
            raise ValueError("Key '%s' not found" % key)

        value = self.get(key, version=version, client=client) - delta
        self.set(key, value, version=version, client=client)
        return value

    def has_key(self, key, version=None):
        """
        Test if key exists.
        """

        key = self.make_key(key, version=version)
        return self._client.exists(key)

    # Other not default and not standar methods.
    def keys(self, search):
        pattern = self.make_key(search)
        return list(set(map(lambda x: x.split(":", 2)[2], self._client.keys(pattern))))


from .hash_ring import HashRing
_findhash = re.compile('.*\{(.*)\}.*', re.I)

class ShardedRedisCache(RedisCache):
    connections = {}
    nodes = []

    def _connect(self):
        if not isinstance(self._server, (tuple, list)):
            raise ImproperlyConfigured("LOCATION must be a list or tuple")

        for location in self._server:
            try:
                host, port, db = location.split(":")
            except ValueError:
                try:
                    host, port = location.split(":")
                    db = 1
                except ValueError:
                    raise ImproperlyConfigured("invalid location string, this must be <host>:<port>:<db>")

            params = {
                'db': db,
                'password': self.password,
            }
            if host == "unix":
                params['unix_socket_path'] = port
            else:
                params['unix_socket_path'] = None
                params['host'], params['port'] = host, int(port)

            connection_pool = ConnectionPoolHandler()\
                .connection_pool(parser_class=self.parser_class, **params)

            self.connections[location] = Redis(connection_pool=connection_pool)
            self.nodes.append(location)

        self.ring = HashRing(self.nodes)

    def get_server_name(self, _key):
        key = str(_key)
        g = _findhash.match(key)
        if g != None and len(g.groups()) > 0:
            key = g.groups()[0]
        name = self.ring.get_node(key)
        return name

    def get_server(self,key):
        name = self.get_server_name(key)
        return self.connections[name]

    def add(self,  key, value, timeout=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).add(key=key, value=value,
                                        version=version, client=client)

    def get(self,  key, default=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)
        return super(ShardedRedisCache, self).get(key=key, default=default,
                                                version=version, client=client)

    def get_many(self, keys, version=None):
        if not keys:
            return {}

        recovered_data = SortedDict()
        new_keys = map(lambda key: self.make_key(key, version=version), keys)
        map_keys = dict(zip(new_keys, keys))

        for key in new_keys:
            client = self.get_server(key)
            value = self.get(key=key, version=version, client=client)

            if value is None:
                continue

            recovered_data[map_keys[key]] = value
        return recovered_data

    def set(self, key, value, timeout=None, version=None, client=None):
        """
        Persist a value to the cache, and set an optional expiration time.
        """
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).set(key=key, value=value, timeout=timeout,
                                                        version=version, client=client)


    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        for key, value in data.iteritems():
            self.set(key, value, timeout, version=version)

    def delete(self, key, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).delete(key=key, version=version, client=client)

    def delete_many(self, keys, version=None):
        """
        Remove multiple keys at once.
        """
        for key in map(lambda key: self.make_key(key, version=version), keys):
            client = self.get_server(key)
            self.delete(key, client=client)

    def incr_version(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).incr_version(key=key, delta=delta,
                                                    version=version, client=client)

    def incr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).incr(key=key, delta=delta,
                                        version=version, client=client)


    def decr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardedRedisCache, self).decr(key=key, delta=delta,
                                        version=version, client=client)
