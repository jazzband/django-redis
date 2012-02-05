# -*- coding: utf-8 -*-

from collections import defaultdict

from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
from django.core.exceptions import ImproperlyConfigured
from django.utils import importlib
from django.utils.encoding import smart_unicode, smart_str
from django.utils.datastructures import SortedDict

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import redis
except ImportError:
    raise InvalidCacheBackendError(
        "Redis cache backend requires the 'redis-py' library")

from redis.connection import UnixDomainSocketConnection, Connection
from redis.connection import DefaultParser

class CacheKey(object):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def __init__(self, key):
        self._key = key

    def __eq__(self, other):
        return self._key == other

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return self.__unicode__()

    def __unicode__(self):
        return smart_str(self._key)


class CacheConnectionPool(object):
    _connection_pool = None

    def get_connection_pool(self, host='127.0.0.1', port=6379, db=1,
                password=None, parser_class=None, unix_socket_path=None):

        if self._connection_pool is None:
            connection_class = unix_socket_path \
                and UnixDomainSocketConnection or Connection

            kwargs = {
                'db': db,
                'password': password,
                'connection_class': connection_class,
                'parser_class': parser_class,
            }

            if unix_socket_path is None:
                kwargs.update({'host': host, 'port': port})
            else:
                kwargs['path'] = unix_socket_path

            self._connection_pool = redis.ConnectionPool(**kwargs)

        return self._connection_pool

# ConnectionPools keyed off the connection parameters
pools = defaultdict(CacheConnectionPool)

class RedisCache(BaseCache):
    _pickle_version = -1

    def __init__(self, server, params):
        """
        Connect to Redis, and set up cache backend.
        """
        self._init(server, params)
        super(RedisCache, self).__init__(params)

    def _init(self, server, params):
        super(RedisCache, self).__init__(params)
        self._server = server
        self._params = params
        self._options = params.get('OPTIONS', {})

        unix_socket_path = None
        if ':' in self.server:
            host, port = self.server.split(':')
            try:
                port = int(port)
            except (ValueError, TypeError):
                raise ImproperlyConfigured("port value must be an integer")

        else:
            host, port = None, None
            unix_socket_path = self.server
        
        if "PICKLE_VERSION" in self._options:
            try:
                self._pickle_version = int(self._options['PICKLE_VERSION'])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

        kwargs = {
            'db': self.db,
            'password': self.password,
            'host': host,
            'port': port,
            'unix_socket_path': unix_socket_path,
        }

        pool_key = ':'.join([str(v) for v in kwargs.values()])

        global pools
        connection_pool = pools[pool_key].get_connection_pool(
            parser_class=self.parser_class, **kwargs)

        self._client = redis.Redis(connection_pool=connection_pool)

    def make_key(self, key, version=None):
        if not isinstance(key, CacheKey):
            key = CacheKey(super(RedisCache, self).make_key(key, version))
        return key

    def incr_version(self, key, delta=1, version=None):
        """
        Adds delta to the cache version for the supplied key. Returns the
        new version.

        Note: In Redis 2.0 you cannot rename a volitle key, so we have to move
        the value from the old key to the new key and maintain the ttl.
        """
        if version is None:
            version = self.version
        old_key = self.make_key(key, version)
        value = self.get(old_key, version=version)
        ttl = self._client.ttl(old_key)
        if value is None:
            raise ValueError("Key '%s' not found" % key)
        new_key = self.make_key(key, version=version+delta)
        # TODO: See if we can check the version of Redis, since 2.2 will be able
        # to rename volitile keys.
        self.set(new_key, value, timeout=ttl)
        self.delete(old_key)
        return version + delta

    @property
    def server(self):
        return self._server or "127.0.0.1:6379"

    @property
    def params(self):
        return self._params or {}

    @property
    def db(self):
        _db = self.params.get('db', self._options.get('DB', 1))
        try:
            _db = int(_db)
        except (ValueError, TypeError):
            raise ImproperlyConfigured("db value must be an integer")
        return _db

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

    def add(self, key, value, timeout=None, version=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        key = self.make_key(key, version=version)
        if self._client.exists(key):
            return False
        return self.set(key, value, timeout)

    def get(self, key, default=None, version=None):
        """
        Retrieve a value from the cache.

        Returns unpickled value if key is found, the default if not.
        """
        key = self.make_key(key, version=version)
        value = self._client.get(key)
        if value is None:
            return default
        try:
            result = int(value)
        except (ValueError, TypeError):
            result = self.unpickle(value)
        return result

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

        try:
            value = float(value)
            # If you lose precision from the typecast to str, then pickle value
            if int(value) != value:
                raise TypeError
        except (ValueError, TypeError):
            result = self._set(key, self.pickle(value), int(timeout), client)
        else:
            result = self._set(key, int(value), int(timeout), client)

        return result

    def delete(self, key, version=None):
        """
        Remove a key from the cache.
        """
        self._client.delete(self.make_key(key, version=version))

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
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = self.unpickle(value)
            if isinstance(value, basestring):
                value = smart_unicode(value)
            recovered_data[map_keys[key]] = value
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

    def incr(self, key, delta=1, version=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        key = self.make_key(key, version=version)
        exists = self._client.exists(key)
        if not exists:
            raise ValueError("Key '%s' not found" % key)
        try:
            value = self._client.incr(key, delta)
        except redis.ResponseError:
            value = self.get(key) + 1
            self.set(key, value)
        return value

    def has_key(self, key, version=None):
        """
        Test if key exists.
        """

        key = self.make_key(key, version=version)
        return self._client.exists(key)

    # Other not default and not standar methods.
    def keys(self, search):
        return list(set(map(lambda x: x.split(":", 2)[2], self._client.keys(search))))
