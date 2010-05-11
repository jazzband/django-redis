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
except:
    raise InvalidCacheBackendError(
        "Redis cache backend requires the 'redis-py' library")


class CacheClass(BaseCache):
    def __init__(self, server, params):
        "Connect to Redis, and set up cache backend."
        BaseCache.__init__(self, params)
        self._cache = redis.Redis(server.split(':')[0], db=1)

    def add(self, key, value, timeout=0):
        """
        Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.
        """
        if self._cache.exists(smart_str(key)):
            return False
        return self.set(smart_str(key), value, timeout)

    def get(self, key, default=None):
        """
        Retrieve a value from the cache.

        Returns unpicked value if key is found, ``None`` if not.
        """
        # get the value from the cache
        value = self._cache.get(smart_str(key))
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
        # pickle the value
        value = base64.encodestring(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)).strip()
        # store the key/value pair
        result = self._cache.set(smart_str(key), value)
        # set expiration if needed
        self.expire(key, timeout)
        # result is a boolean
        return result

    def expire(self, key, timeout=None):
        """
        set content expiration, if necessary
        """
        timeout = timeout or self.default_timeout
        self._cache.expire(smart_str(key), timeout)

    def delete(self, key):
        "Remove a key from the cache."
        self._cache.delete(smart_str(key))

    def delete_many(self, keys):
        self._cache.delete(*map(smart_str, keys))

    def clear(self):
        self._cache.flushdb()

    def get_many(self, keys):
        """
        Retrieve many keys.
        """
        decoded_results = SortedDict()
        results = self._cache.mget(map(lambda k: smart_str(k), keys))
        for key, value in zip(keys, results):
            if value is None:
                continue
            # pickle doesn't want a unicode!
            value = smart_str(value)
            # hydrate that pickle
            value = pickle.loads(base64.decodestring(value))
            if isinstance(value, basestring):
                value = smart_unicode(value)
            decoded_results[key] = value
        return decoded_results

    def set_many(self, data, timeout=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs.  For certain backends (memcached), this is much more efficient
        than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        safe_data = {}
        for key, value in data.iteritems():
            safe_data[smart_str(key)] = base64.encodestring(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)).strip()
        self._cache.mset(safe_data)
        map(self.expire, safe_data, [timeout]*len(safe_data))

    def close(self, **kwargs):
        """
        Disconnect from the cache.
        """
        self._cache.connection.disconnect()
