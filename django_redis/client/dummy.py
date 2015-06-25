import re
import fnmatch

from django.core.cache.backends.locmem import LocMemCache


class RedisDummyCache(LocMemCache):
    """
    Useful for testing, use it like:

    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.RedisDummyCache',
            }
        }
    }
    """
    def __init__(self, *args, **kwargs):
        super(RedisDummyCache, self).__init__(name='', params={})

    def get(self, key, default, version, client):
        return super(RedisDummyCache, self).get(
            key=key, default=default, version=version
        )

    def delete_pattern(self, pattern):
        regex = re.compile(fnmatch.translate(':*:' + pattern))
        for key in self._cache.keys():
            if regex.match(key):
                with self._lock.writer():
                    self._delete(key)
