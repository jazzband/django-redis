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

    def _prepare_key(self, raw_key):
        "``smart_str``-encode the key."
        return smart_str(raw_key)

    def _prepare_value(self, value):
        return value

    def add(self, key, value, timeout=0):
        """Add a value to the cache, failing if the key already exists.

        Returns ``True`` if the object was added, ``False`` if not.

        """

        if self._cache.exists(key):
            return False

        return self.set(key, value, timeout)

    def get(self, key, default=None):
        """Retrieve a value from the cache.

        Returns unpicked value if key is found, ``None`` if not.

        """

        key = self._prepare_key(key)

        # get the value from the cache
        value = self._cache.get(key)

        if value is None:
            return default

        # picke doesn't want a unicode!
        value = smart_str(value)

        # hydrate that pickle
        value = pickle.loads(value.decode('base64'))

        if isinstance(value, basestring):
            return smart_unicode(value)
        else:
            return value

    def set(self, key, value, timeout=None):
        "Persist a value to the cache, and set an optional expiration time."

        key = self._prepare_key(key)
        value = self._prepare_value(value)

        # pickle the value
        value = pickle.dumps(value).encode('base64')

        # store the key/value pair
        result = self._cache.set(key, value)

        # set content expiration, if necessary
        if timeout is None or timeout is not False:
            timeout = timeout or self.default_timeout
            self._cache.expire(key, timeout)

        # result is a boolean
        return result

    def delete(self, key):
        "Remove a key from the cache."
        key = self._prepare_key(key)
        self._cache.delete(key)

    def flush(self, all_dbs=False):
        self._cache.flush(all_dbs)

    def get_many(self, keys):
        "Retrieve many keys."
        return self._cache.mget(map(self._prepare_key, keys))

    def incr(self, key, delta=1):
        "Atomically increment ``key`` by ``delta``."
        key = self._prepare_key(key)
        return self._cache.incr(key, delta)

    def decr(self, key, delta=1):
        "Atomically decrement ``key`` by ``delta``."
        key = self._prepare_key(key)
        return self._cache.decr(key, delta)

    def close(self, **kwargs):
        "Disconnect from the cache."
        self._cache.connection.disconnect()
