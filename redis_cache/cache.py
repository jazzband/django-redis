from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
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


class CacheClass(BaseCache):
    def __init__(self, server, params):
        """
        Connect to Redis, and set up cache backend.
        """
        BaseCache.__init__(self, params)
        db = params.get('OPTIONS', {}).get('db', 1)
        try:
            db = int(db)
        except (ValueError, TypeError):
            db = 1
        password = params.get('password', None)
        if ':' in server:
            host, port = server.split(':')
            try:
                port = int(port)
            except (ValueError, TypeError):
                port = 6379
        else:
            host = 'localhost'
            port = 6379
        self._cache = redis.Redis(host=host, port=port, db=db, password=password)

    def make_key(self, key, version=None):
        """
        Returns the utf-8 encoded bytestring of the given key.
        """
        return smart_str(super(CacheClass, self).make_key(key, version))

    def add(self, key, value, timeout=None, version=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        _key = key
        key = self.make_key(key, version=version)
        if self._cache.exists(key):
            return False
        return self.set(_key, value, timeout)

    def get(self, key, default=None, version=None):
        """
        Retrieve a value from the cache.

        Returns unpicked value if key is found, ``None`` if not.
        """
        # get the value from the cache
        value = self._cache.get(self.make_key(key, version=version))
        if value is None:
            return default
        # pickle doesn't want a unicode!
        value = smart_str(value)
        # hydrate that pickle
        return pickle.loads(value)

    def set(self, key, value, timeout=None, version=None):
        """
        Persist a value to the cache, and set an optional expiration time.
        """
        _key = key
        key = self.make_key(key, version=version)
        # store the pickled value
        result = self._cache.set(key, pickle.dumps(value))
        # set expiration if needed
        self.expire(_key, timeout, version=version)
        # result is a boolean
        return result

    def expire(self, key, timeout=None, version=None):
        """
        Set content expiration, if necessary
        """
        _key = key
        key = self.make_key(key, version=version)
        if timeout == 0:
            # force the key to be non-volatile
            result = self._cache.get(key)
            self._cache.set(key, result)
        else:
            timeout = timeout or self.default_timeout
            # If the expiration command returns false, we need to reset the key
            # with the new expiration
            if not self._cache.expire(key, timeout):
                value = self.get(_key, version=version)
                self.set(_key, value, timeout, version=version)

    def delete(self, key, version=None):
        """
        Remove a key from the cache.
        """
        self._cache.delete(self.make_key(key, version))

    def delete_many(self, keys, version=None):
        """
        Remove multiple keys at once.
        """
        if keys:
            l = lambda x: self.make_key(x, version=version)
            self._cache.delete(*map(l, keys))

    def clear(self):
        """
        Flush all cache keys.
        """
        self._cache.flushdb()

    def get_many(self, keys, version=None):
        """
        Retrieve many keys.
        """
        recovered_data = SortedDict()
        new_keys = map(lambda x: self.make_key(x, version=version), keys)
        results = self._cache.mget(new_keys)
        map_keys = dict(zip(new_keys, keys))
        for key, value in zip(new_keys, results):
            if value is None:
                continue
            # pickle doesn't want a unicode!
            value = smart_str(value)
            # hydrate that pickle
            value = pickle.loads(value)
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
        safe_data = {}
        for key, value in data.iteritems():
            safe_data[key] = pickle.dumps(value)
        if safe_data:
            self._cache.mset(dict((self.make_key(key, version=version), value)
                                   for key, value in safe_data.iteritems()))
            map(self.expire, safe_data, [timeout]*len(safe_data))

    def close(self, **kwargs):
        """
        Disconnect from the cache.
        """
        self._cache.connection.disconnect()

    def incr_version(self, key, delta=1, version=None):
        """Adds delta to the cache version for the supplied key. Returns the
        new version.
        """
        if version is None:
            version = self.version

        value = self.get(key, version=version)
        if value is None:
            raise ValueError("Key '%s' not found" % key)

        self._cache.rename(self.make_key(key, version), self.make_key(key,
            version=version+delta))
        return version+delta