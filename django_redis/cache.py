import functools
import logging
import time
from threading import RLock

from django.conf import settings
from django.core.cache.backends.base import BaseCache

from .exceptions import ConnectionInterrupted
from .util import load_class

DJANGO_REDIS_IGNORE_EXCEPTIONS = getattr(settings, "DJANGO_REDIS_IGNORE_EXCEPTIONS", False)
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = getattr(settings, "DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS", False)
DJANGO_REDIS_LOGGER = getattr(settings, "DJANGO_REDIS_LOGGER", False)
DJANGO_REDIS_SCAN_ITERSIZE = getattr(settings, "DJANGO_REDIS_SCAN_ITERSIZE", 10)
DJANGO_REDIS_EXCEPTION_THRESHOLD = getattr(settings, "DJANGO_REDIS_EXCEPTION_THRESHOLD", None)
DJANGO_REDIS_EXCEPTION_THRESHOLD_TIME_WINDOW = getattr(settings, "DJANGO_REDIS_EXCEPTION_TIME_WINDOW", 1)
DJANGO_REDIS_EXCEPTION_THRESHOLD_COOLDOWN = getattr(settings, "DJANGO_REDIS_EXCEPTION_THRESHOLD_COOLDOWN", 5)


if DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS:
    logger = logging.getLogger((DJANGO_REDIS_LOGGER or __name__))


def omit_exception(method=None, return_value=None):
    """
    Simple decorator that intercepts connection
    errors and ignores these if settings specify this.
    """

    if method is None:
        return functools.partial(omit_exception, return_value=return_value)

    @functools.wraps(method)
    def _decorator(self, *args, **kwargs):
        try:
            if self._exception_threshold and self._exception_threshold_hit():
                if DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS:
                    logger.error("Django Redis exception threshold reached! Skipping cache call.")
                    return return_value

            return method(self, *args, **kwargs)
        except ConnectionInterrupted as e:
            if self._exception_threshold:
                self._incr_exception_counter()
            if self._ignore_exceptions:
                if DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS:
                    logger.error(str(e))

                return return_value
            raise e.parent
    return _decorator


class RedisCache(BaseCache):
    def __init__(self, server, params):
        super(RedisCache, self).__init__(params)
        self._server = server
        self._params = params

        options = params.get("OPTIONS", {})
        self._client_cls = options.get("CLIENT_CLASS", "django_redis.client.DefaultClient")
        self._client_cls = load_class(self._client_cls)
        self._client = None

        self._ignore_exceptions = options.get("IGNORE_EXCEPTIONS", DJANGO_REDIS_IGNORE_EXCEPTIONS)
        self._exception_threshold = options.get("EXCEPTION_THRESHOLD", DJANGO_REDIS_EXCEPTION_THRESHOLD)
        if self._exception_threshold is not None:
            self._exception_threshold = float(self._exception_threshold)
        self._exception_threshold_cooldown = float(options.get(
            "EXCEPTION_THRESHOLD_COOLDOWN", DJANGO_REDIS_EXCEPTION_THRESHOLD_COOLDOWN))
        self._exception_threshold_time_window = float(options.get(
            "EXCEPTION_THRESHOLD_TIME_WINDOW", DJANGO_REDIS_EXCEPTION_THRESHOLD_TIME_WINDOW))
        RedisCache._window_end_time = (time.time() + self._exception_threshold_time_window)

    _exception_counter_lock = RLock()
    _exception_counter = 0
    _exception_threshold_reset_at_time = None
    _window_end_time = None

    def _incr_exception_counter(self):
        now = time.time()
        with RedisCache._exception_counter_lock:
            if RedisCache._exception_threshold_reset_at_time:
                # threshold already hit don't do anything
                return

            if RedisCache._window_end_time < now:
                # if past window, reset everything
                RedisCache._exception_counter = 0
                RedisCache._window_end_time = (time.time() + self._exception_threshold_time_window)

            if RedisCache._exception_counter > self._exception_threshold:
                # exceeded threshold
                RedisCache._exception_threshold_reset_at_time = (
                    time.time() + self._exception_threshold_cooldown)
                RedisCache._exception_counter = 0
            else:
                RedisCache._exception_counter += 1

    @staticmethod
    def _exception_threshold_hit():
        now = time.time()

        if not RedisCache._exception_threshold_reset_at_time:
            return False

        if RedisCache._exception_threshold_reset_at_time >= now:
            return True

        with RedisCache._exception_counter_lock:
            # reset threshold
            RedisCache._exception_threshold_reset_at_time = None
        return False

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

    @omit_exception
    def get(self, key, default=None, version=None, client=None):
        try:
            return self.client.get(key, default=default, version=version,
                                   client=client)
        except ConnectionInterrupted as e:
            if DJANGO_REDIS_IGNORE_EXCEPTIONS or self._ignore_exceptions:
                if DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS:
                    logger.error(str(e))
                return default
            raise

    @omit_exception
    def delete(self, *args, **kwargs):
        return self.client.delete(*args, **kwargs)

    @omit_exception
    def delete_pattern(self, *args, **kwargs):
        kwargs['itersize'] = kwargs.get('itersize', DJANGO_REDIS_SCAN_ITERSIZE)
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
    def persist(self, *args, **kwargs):
        return self.client.persist(*args, **kwargs)

    @omit_exception
    def expire(self, *args, **kwargs):
        return self.client.expire(*args, **kwargs)

    @omit_exception
    def lock(self, *args, **kwargs):
        return self.client.lock(*args, **kwargs)

    @omit_exception
    def close(self, **kwargs):
        self.client.close(**kwargs)
