import functools
import logging
from typing import Any, Callable, Dict, Optional

from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.core.cache.backends.base import BaseCache
from django.utils.module_loading import import_string

from .exceptions import ConnectionInterrupted

DJANGO_REDIS_SCAN_ITERSIZE = getattr(settings, "DJANGO_REDIS_SCAN_ITERSIZE", 10)

CONNECTION_INTERRUPTED = object()


def omit_exception(
    method: Optional[Callable] = None, return_value: Optional[Any] = None
):
    """
    Simple decorator that intercepts connection
    errors and ignores these if settings specify this.
    """

    if method is None:
        return functools.partial(omit_exception, return_value=return_value)

    @functools.wraps(method)
    def _decorator(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ConnectionInterrupted as e:
            if self._ignore_exceptions:
                if self._log_ignored_exceptions:
                    self.logger.error(str(e))

                return return_value
            raise e.__cause__

    return _decorator


class RedisCache(BaseCache):
    def __init__(self, server: str, params: Dict[str, Any]) -> None:
        super().__init__(params)
        self._server = server
        self._params = params

        options = params.get("OPTIONS", {})
        self._client_cls = options.get(
            "CLIENT_CLASS", "django_redis.client.DefaultClient"
        )
        self._client_cls = import_string(self._client_cls)
        self._client = None

        self._ignore_exceptions = options.get(
            "IGNORE_EXCEPTIONS",
            getattr(settings, "DJANGO_REDIS_IGNORE_EXCEPTIONS", False),
        )
        self._log_ignored_exceptions = getattr(
            settings, "DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS", False
        )
        self.logger = (
            logging.getLogger(getattr(settings, "DJANGO_REDIS_LOGGER", __name__))
            if self._log_ignored_exceptions
            else None
        )

    @property
    def client(self):
        """
        Lazy client connection property.
        """
        if self._client is None:
            self._client = self._client_cls(self._server, self._params, self)
        return self._client

    @omit_exception
    def set(self, *args, **kwargs):
        return self.client.set(*args, **kwargs)

    @omit_exception
    def incr_version(self, *args, **kwargs):
        return self.client.incr_version(*args, **kwargs)

    @omit_exception
    def add(self, *args, **kwargs):
        return self.client.add(*args, **kwargs)

    def get(self, key, default=None, version=None, client=None):
        value = self._get(key, default, version, client)
        if value is CONNECTION_INTERRUPTED:
            value = default
        return value

    @omit_exception(return_value=CONNECTION_INTERRUPTED)
    def _get(self, key, default, version, client):
        return self.client.get(key, default=default, version=version, client=client)

    @omit_exception
    def delete(self, *args, **kwargs):
        """returns a boolean instead of int since django version 3.1"""
        result = self.client.delete(*args, **kwargs)
        return bool(result) if DJANGO_VERSION >= (3, 1, 0) else result

    @omit_exception
    def delete_pattern(self, *args, **kwargs):
        kwargs["itersize"] = kwargs.get("itersize", DJANGO_REDIS_SCAN_ITERSIZE)
        return self.client.delete_pattern(*args, **kwargs)

    @omit_exception
    def delete_many(self, *args, **kwargs):
        return self.client.delete_many(*args, **kwargs)

    @omit_exception
    def clear(self):
        return self.client.clear()

    @omit_exception(return_value={})
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
    def iter_keys(self, *args, **kwargs):
        return self.client.iter_keys(*args, **kwargs)

    @omit_exception
    def ttl(self, *args, **kwargs):
        return self.client.ttl(*args, **kwargs)

    @omit_exception
    def pttl(self, *args, **kwargs):
        return self.client.pttl(*args, **kwargs)

    @omit_exception
    def persist(self, *args, **kwargs):
        return self.client.persist(*args, **kwargs)

    @omit_exception
    def expire(self, *args, **kwargs):
        return self.client.expire(*args, **kwargs)

    @omit_exception
    def expire_at(self, *args, **kwargs):
        return self.client.expire_at(*args, **kwargs)

    @omit_exception
    def pexpire(self, *args, **kwargs):
        return self.client.pexpire(*args, **kwargs)

    @omit_exception
    def pexpire_at(self, *args, **kwargs):
        return self.client.pexpire_at(*args, **kwargs)

    @omit_exception
    def lock(self, *args, **kwargs):
        return self.client.lock(*args, **kwargs)

    @omit_exception
    def close(self, **kwargs):
        self.client.close(**kwargs)

    @omit_exception
    def touch(self, *args, **kwargs):
        return self.client.touch(*args, **kwargs)
