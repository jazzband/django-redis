# -*- coding: utf-8 -*-

from django.conf import settings
try:
    from django.utils.timezone import now as datetime_now
    assert datetime_now
except ImportError:
    import datetime
    datetime_now = datetime.datetime.now
from .default import DefaultClient
from ..exceptions import ConnectionInterrumped
import functools


def auto_failover(method):
    """
    Simple decorator that intercepts connection
    errors and ignores these if settings specify this.
    """

    @functools.wraps(method)
    def _decorator(self, *args, **kwargs):
        if self._in_fallback:
            pass_seconds = (datetime_now() - self._in_fallback_date).total_seconds()
            if pass_seconds > self._options.get("FAILOVER_TIME", 30):
                print("Go to default connection")
                self._client = self._old_client

                self._in_fallback = False
                self._in_fallback_date = None
                del self.fallback_client
            else:
                print("Mantain fallback connection")

        try:
            print("Executing {0}".format(method.__name__))
            return method(self, *args, **kwargs)
        except ConnectionInterrumped:
            if self._fallback and not self._in_fallback:
                print("raised ConnectionInterrumped")
                print("Switching to fallback conection")
                self._old_client = self._client
                self._client = self.fallback_client

                self._in_fallback = True
                self._in_fallback_date = datetime_now()

            return method(self, *args, **kwargs)
    return _decorator


class SimpleFailoverClient(DefaultClient):
    _in_fallback_date = None
    _in_fallback = False

    @property
    def fallback_client(self):
        if hasattr(self, "_fallback_client"):
            return self._fallback_client

        _fallback_client = self._connect(*self._fallback_params)
        self._fallback_client = _fallback_client
        return _fallback_client

    @fallback_client.deleter
    def fallback_client(self):
        if hasattr(self, "_fallback_client"):
            del self._fallback_client

    def connect(self):
        if "/" in self._server:
            self._server, self._fallback = [x.strip() for x in self._server.split("/", 1)]

        host, port, db = self.parse_connection_string(self._server)

        # Check syntax of connection string.
        self._fallback_params = self.parse_connection_string(self._fallback)

        connection = self._connect(host, port, db)
        return connection

    @auto_failover
    def set(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).set(*args, **kwargs)

    @auto_failover
    def incr_version(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).incr_version(*args, **kwargs)

    @auto_failover
    def add(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).add(*args, **kwargs)

    @auto_failover
    def get(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).get(*args, **kwargs)

    @auto_failover
    def delete(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).delete(*args, **kwargs)

    @auto_failover
    def delete_pattern(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).delete_pattern(*args, **kwargs)

    @auto_failover
    def delete_many(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).delete_many(*args, **kwargs)

    @auto_failover
    def clear(self):
        return super(SimpleFailoverClient, self).clear()

    @auto_failover
    def get_many(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).get_many(*args, **kwargs)

    @auto_failover
    def set_many(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).set_many(*args, **kwargs)

    @auto_failover
    def incr(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).incr(*args, **kwargs)

    @auto_failover
    def decr(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).decr(*args, **kwargs)

    @auto_failover
    def has_key(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).has_key(*args, **kwargs)

    @auto_failover
    def keys(self, *args, **kwargs):
        return super(SimpleFailoverClient, self).keys(*args, **kwargs)

    @auto_failover
    def close(self, **kwargs):
        super(SimpleFailoverClient, self).close(**kwargs)
