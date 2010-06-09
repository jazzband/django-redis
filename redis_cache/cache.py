import base64
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
        db = params.get('db', 1)
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

    def prepare_key(self, key):
        """
        Hashes the key if length is greater than 250.
        """
        return smart_str(key)

    def add(self, key, value, timeout=None):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        key = self.prepare_key(key)
        if self._cache.exists(key):
            return False
        return self.set(key, value, timeout)

    def get(self, key, default=None):
        """
        Retrieve a value from the cache.

        Returns unpicked value if key is found, ``None`` if not.
        """
        # get the value from the cache
        value = self._cache.get(self.prepare_key(key))
        if value is None:
            return default
        # pickle doesn't want a unicode!
        value = smart_str(value)
        # hydrate that pickle
        return pickle.loads(base64.decodestring(value))

    def set(self, key, value, timeout=None):
        """
        Persist a value to the cache, and set an optional expiration time.
        """
        key = self.prepare_key(key)
        # pickle the value
        value = base64.encodestring(
            pickle.dumps(value, pickle.HIGHEST_PROTOCOL)).strip()
        # store the key/value pair
        result = self._cache.set(key, value)
        # set expiration if needed
        self.expire(key, timeout)
        # result is a boolean
        return result

    def expire(self, key, timeout=None):
        """
        Set content expiration, if necessary
        """
        if timeout is None:
            timeout = self.default_timeout
        self._cache.expire(key, timeout)

    def delete(self, key):
        """
        Remove a key from the cache.
        """
        self._cache.delete(self.prepare_key(key))

    def delete_many(self, keys):
        """
        Remove multiple keys at once.
        """
        if keys:
            self._cache.delete(*map(self.prepare_key, keys))

    def clear(self):
        """
        Flush all cache keys.
        """
        self._cache.flushdb()

    def get_many(self, keys):
        """
        Retrieve many keys.
        """
        recovered_data = SortedDict()
        results = self._cache.mget(map(lambda k: self.prepare_key(k), keys))
        for key, value in zip(keys, results):
            if value is None:
                continue
            # pickle doesn't want a unicode!
            value = smart_str(value)
            # hydrate that pickle
            value = pickle.loads(base64.decodestring(value))
            if isinstance(value, basestring):
                value = smart_unicode(value)
            recovered_data[key] = value
        return recovered_data

    def set_many(self, data, timeout=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        safe_data = {}
        for key, value in data.iteritems():
            safe_data[self.prepare_key(key)] = base64.encodestring(
                pickle.dumps(value, pickle.HIGHEST_PROTOCOL)).strip()
        if safe_data:
            self._cache.mset(safe_data)
            map(self.expire, safe_data, [timeout]*len(safe_data))

    def close(self, **kwargs):
        """
        Disconnect from the cache.
        """
        self._cache.connection.disconnect()
