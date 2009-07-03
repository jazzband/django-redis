"Redis cache backend"
import client
try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
from django.utils.encoding import smart_unicode, smart_str


class CacheClass(BaseCache):
    def __init__(self, server, params):
        BaseCache.__init__(self, params)
        self._cache = redis_client.Redis(server.split(':')[0], db=1)

    def add(self, key, value, timeout=0):
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        success = self._cache.set(smart_str(key), pickle.dumps(value)) == "OK"
        return success and timeout and self._cache.expire(smart_str(key), timeout or self.default_timeout) == 1

    def get(self, key, default=None):
        val = self._cache.get(smart_str(key))
        if val is None:
            return default
        else:
            val = pickle.loads(val)
            if isinstance(val, basestring):
                return smart_unicode(val)
            else:
                return val

    def set(self, key, value, timeout=0):
        return self.add(key, value, timeout)

    def delete(self, key):
        self._cache.delete(smart_str(key))

    def get_many(self, keys):
        return self._cache.mget(map(smart_str, keys))

    def close(self, **kwargs):
        self._cache.disconnect()

    def incr(self, key, delta=1):
        return self._cache.incr(key, delta)

    def decr(self, key, delta=1):
        return self._cache.decr(key, delta)
