# -*- coding: utf-8 -*-

from django.conf import settings
from django.core.cache.backends.base import BaseCache
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import get_cache

from redis.exceptions import ConnectionError
from .util import load_class
from .exceptions import ConnectionInterrumped

import functools

DJANGO_REDIS_IGNORE_EXCEPTIONS = getattr(settings,
            'DJANGO_REDIS_IGNORE_EXCEPTIONS', False)


def omit_exception(method):
    """
    Simple decorator that intercepts connection
    errors and ignores these if settings specify this.
    """

    @functools.wraps(method)
    def _decorator(self, *args, **kwargs):
        if DJANGO_REDIS_IGNORE_EXCEPTIONS:
            try:
                return method(self, *args, **kwargs)
            except ConnectionInterrumped:
                if "default" in kwargs:
                    return kwargs["default"]
                return None

        return method(self, *args, **kwargs)
    return _decorator


class RedisCache(BaseCache):
    def __init__(self, server, params):
        super(RedisCache, self).__init__(params)
        self._server = server
        self._params = params

        options = params.get('OPTIONS', {})
        self._client_cls = options.get('CLIENT_CLASS', 'redis_cache.client.DefaultClient')
        self._client_cls = load_class(self._client_cls)
        self._client = None

        self._fallback_name = options.get('FALLBACK', None)
        self._fallback = None
        self._fallback_counter = 0
        self._on_fallback = False

    @property
    def client(self):
        """
        Lazy client connection property.
        """
        if self._client is None:
            self._client = self._client_cls(self._server, self._params, self)
        return self._client

    @property
    def raw_client(self):
        """
        Return a raw redis client (connection). Not all
        pluggable clients supports this feature. If not supports
        this raises NotImplementedError
        """
        return self.client.client

    @property
    def fallback_client(self):
        """
        Used in fallback mode on the primary client does not
        connect to the server.
        """

        if self._fallback is None:
            try:
                self._fallback = get_cache(self._fallback_name)
            except TypeError:
                raise ImproperlyConfigured("%s cache backend is not configured" % (self._fallback_name))
        return self._fallback

    @omit_exception
    def set(self, *args, **kwargs):
        return self.client.set(*args, **kwargs)

    @omit_exception
    def incr_version(self, *args, **kwargs):
        return self.client.incr_version(*args, **kwargs)

    @omit_exception
    def add(self, *args, **kwargs):
        return self.client.add(*args, **kwargs)

    @omit_exception
    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)

    @omit_exception
    def delete(self, *args, **kwargs):
        return self.client.delete(*args, **kwargs)

    @omit_exception
    def delete_pattern(self, *args, **kwargs):
        return self.client.delete_pattern(*args, **kwargs)

    @omit_exception
    def delete_many(self, *args, **kwargs):
        return self.client.delete_many(*args, **kwargs)

    @omit_exception
    def clear(self):
        return self.client.clear()

    @omit_exception
    def get_many(self, *args, **kwargs):
        return self.client.get_many(*args, **kwargs)

    @omit_exception
    def set_many(self, *args, **kwargs):
        return self.client.set_many(*args, **kwargs)

    @omit_exception
    def incr(self, *args, **kwargs):
        return self.client.incr(*args, **kwargs)

    @omit_exception
    def decr(self, *args, **kwargs):
        return self.client.decr(*args, **kwargs)

    @omit_exception
    def has_key(self, *args, **kwargs):
        return self.client.has_key(*args, **kwargs)

    @omit_exception
    def keys(self, *args, **kwargs):
        return self.client.keys(*args, **kwargs)

    @omit_exception
    def close(self, **kwargs):
        self.client.close(**kwargs)
