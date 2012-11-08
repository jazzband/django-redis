# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.core.exceptions import ImproperlyConfigured

try:
    from django.utils.encoding import smart_bytes
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes

from django.utils.datastructures import SortedDict
from django.utils import importlib

try:
    import cPickle as pickle
except ImportError:
    import pickle

from collections import defaultdict
import functools
import re

from redis import Redis
from redis import ConnectionPool
from redis.exceptions import ConnectionError
from redis.connection import DefaultParser
from redis.connection import UnixDomainSocketConnection, Connection

from .util import CacheKey, load_class
from .hash_ring import HashRing
from .exceptions import ConnectionInterrumped


class DefaultClient(object):
    def __init__(self, server, params, backend):
        self._pickle_version = -1
        self._backend = backend
        self._server = server
        self._params = params

        if not self._server:
            raise ImproperlyConfigured("Missing connections string")

        self._options = params.get('OPTIONS', {})
        self.setup_pickle_version()

    def __contains__(self, key):
        return self.has_key(key)

    @property
    def client(self):
        if hasattr(self, "_client"):
            return self._client

        _client = self.connect()
        self._client = _client
        return _client

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
            port = int(port) if host != "unix" else port
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

        connection_pool = ConnectionPool(**kwargs)
        connection = Redis(connection_pool=connection_pool)
        return connection

    def connect(self):
        host, port, db = self.parse_connection_string(self._server)
        connection = self._connect(host, port, db)
        return connection

    def setup_pickle_version(self):
        if "PICKLE_VERSION" in self._options:
            try:
                self._pickle_version = int(self._options['PICKLE_VERSION'])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def set(self, key, value, timeout=None, version=None, client=None):
        """
        Persist a value to the cache, and set an optional expiration time.
        """

        if not client:
            client = self.client

        key = self.make_key(key, version=version)
        value = self.pickle(value)

        if timeout is None:
            timeout = self._backend.default_timeout

        try:
            if timeout > 0:
                return client.setex(key, value, int(timeout))
            return client.set(key, value)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def incr_version(self, key, delta=1, version=None, client=None):
        """
        Adds delta to the cache version for the supplied key. Returns the
        new version.
        """

        if client is None:
            client = self.client

        if version is None:
            version = self._backend.version

        old_key = self.make_key(key, version)
        value = self.get(old_key, version=version, client=client)

        try:
            ttl = client.ttl(old_key)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

        if value is None:
            raise ValueError("Key '%s' not found" % key)

        if isinstance(key, CacheKey):
            new_key = self.make_key(key.original_key(), version=version + delta)
        else:
            new_key = self.make_key(key, version=version + delta)

        self.set(new_key, value, timeout=ttl, client=client)
        self.delete(old_key, client=client)
        return version + delta

    def add(self, key, value, timeout=None, version=None, client=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        if client is None:
            client = self.client

        key = self.make_key(key, version=version)

        try:
            if client.exists(key):
                return False
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

        return self.set(key, value, timeout, client=client)

    def get(self, key, default=None, version=None, client=None):
        """
        Retrieve a value from the cache.

        Returns unpickled value if key is found, the default if not.
        """
        if client is None:
            client = self.client

        key = self.make_key(key, version=version)

        try:
            value = client.get(key)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

        if value is None:
            return default

        return self.unpickle(value)

    def delete(self, key, version=None, client=None):
        """
        Remove a key from the cache.
        """
        if client is None:
            client = self.client

        try:
            client.delete(self.make_key(key, version=version))
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete_pattern(self, pattern, version=None, client=None):
        """
        Remove all keys matching pattern.
        """

        if client is None:
            client = self.client

        pattern = self.make_key(pattern, version=version)
        try:
            keys = client.keys(pattern)

            if keys:
                client.delete(*keys)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete_many(self, keys, version=None, client=None):
        """
        Remove multiple keys at once.
        """

        if client is None:
            client = self.client

        if not keys:
            return

        keys = map(lambda key: self.make_key(key, version=version), keys)
        try:
            client.delete(*keys)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def clear(self, client=None):
        """
        Flush all cache keys.
        """
        if client is None:
            client = self.client

        client.flushdb()

    def unpickle(self, value):
        """
        Unpickles the given value.
        """
        value = smart_bytes(value)
        return pickle.loads(value)

    def pickle(self, value):
        """
        Pickle the given value.
        """
        return pickle.dumps(value, self._pickle_version)

    def get_many(self, keys, version=None, client=None):
        """
        Retrieve many keys.
        """

        if client is None:
            client = self.client

        if not keys:
            return {}

        recovered_data = SortedDict()

        new_keys = list(map(lambda key: self.make_key(key, version=version), keys))
        map_keys = dict(zip(new_keys, keys))

        try:
            results = client.mget(*new_keys)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

        for key, value in zip(new_keys, results):
            if value is None:
                continue
            recovered_data[map_keys[key]] = self.unpickle(value)
        return recovered_data

    def set_many(self, data, timeout=None, version=None, client=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        if client is None:
            client = self.client

        try:
            pipeline = client.pipeline()
            for key, value in data.items():
                self.set(key, value, timeout, version=version, client=pipeline)
            pipeline.execute()
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def incr(self, key, delta=1, version=None, client=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """

        if client is None:
            client = self.client

        key = self.make_key(key, version=version)

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
            client = self.client

        key = self.make_key(key, version=version)

        if not self.has_key(key):
            raise ValueError("Key '%s' not found" % key)

        value = self.get(key, version=version, client=client) - delta
        self.set(key, value, version=version, client=client)
        return value

    def has_key(self, key, version=None, client=None):
        """
        Test if key exists.
        """

        if client is None:
            client = self.client

        key = self.make_key(key, version=version)
        try:
            return client.exists(key)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    # Other not default and not standar methods.
    def keys(self, search, client=None):
        if client is None:
            client = self.client

        pattern = self.make_key(search)
        try:
            encoding_map = map(lambda x:  x.decode('utf-8'), client.keys(pattern))
            return list(map(lambda x: x.split(":", 2)[2], encoding_map))
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def make_key(self, key, version=None):
        if not isinstance(key, CacheKey):
            key = CacheKey(self._backend.make_key(key, version))
        return key

    def close(self, **kwargs):
        for c in self.client.connection_pool._available_connections:
            c.disconnect()
        del self._client


class ShardClient(DefaultClient):
    _findhash = re.compile('.*\{(.*)\}.*', re.I)

    def __init__(self, *args, **kwargs):
        super(ShardClient, self).__init__(*args, **kwargs)

        if not isinstance(self._server, (list, tuple)):
            self._server = [self._server]

        self._ring = HashRing(self._server)
        self._serverdict = self.connect()

    @property
    def client(self):
        raise NotImplementedError

    def connect(self):
        connection_dict = {}
        for name in self._server:
            host, port, db = self.parse_connection_string(name)
            connection_dict[name] = self._connect(host, port, db)

        return connection_dict

    def get_server_name(self, _key):
        key = str(_key)
        g = self._findhash.match(key)
        if g is not None and len(g.groups()) > 0:
            key = g.groups()[0]
        name = self._ring.get_node(key)
        return name

    def get_server(self, key):
        name = self.get_server_name(key)
        return self._serverdict[name]

    def add(self,  key, value, timeout=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .add(key=key, value=value, version=version, client=client)

    def get(self,  key, default=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .get(key=key, default=default, version=version, client=client)

    def get_many(self, keys, version=None):
        if not keys:
            return {}

        recovered_data = SortedDict()

        new_keys = [self.make_key(key, version=version) for key in keys]
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

        return super(ShardClient, self)\
            .set(key=key, value=value, timeout=timeout, version=version, client=client)

    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        for key, value in data.items():
            self.set(key, value, timeout, version=version)

    def has_key(self, key, version=None, client=None):
        """
        Test if key exists.
        """

        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        key = self.make_key(key, version=version)
        try:
            return client.exists(key)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete(self, key, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self).delete(key=key, version=version, client=client)

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

        return super(ShardClient, self)\
            .incr_version(key=key, delta=delta, version=version, client=client)

    def incr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .incr(key=key, delta=delta, version=version, client=client)

    def decr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .decr(key=key, delta=delta, version=version, client=client)


    def keys(self, search):
        pattern = self.make_key(search)

        keys = []
        for server, connection in self._serverdict.items():
            keys.extend(connection.keys(pattern))

        try:
            encoding_map = map(lambda x:  x.decode('utf-8'), keys)
            return list(map(lambda x: x.split(":", 2)[2], encoding_map))
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete_pattern(self, pattern, version=None):
        """
        Remove all keys matching pattern.
        """

        pattern = self.make_key(pattern, version=version)

        keys = []
        for server, connection in self._serverdict.items():
            keys.extend(connection.keys(pattern))

        if keys:
            for server, connection in self._serverdict.items():
                connection.delete(*keys)

    def close(self):
        pass
