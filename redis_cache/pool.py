# -*- coding: utf-8 -*-

from django.conf import settings

from redis import Redis
from redis.connection import Connection
from redis.connection import DefaultParser
from redis.connection import UnixDomainSocketConnection

from . import util


class ConnectionFactory(object):
    def __init__(self, options):
        pool_cls_path = options.get("CONNECTION_POOL_CLASS",
                                    "redis.connection.ConnectionPool")
        self.pool_cls = util.load_class(pool_cls_path)
        self.pool_cls_kwargs = options.get("CONNECTION_POOL_KWARGS", {})
        self.options = options

        self._pools = {}

    def connect(self, host, port, db):
        """
        Given a basic connection parameters,
        return a new connection.
        """
        kwargs = {
            "db": db,
            "parser_class": self.get_parser_cls(),
            "password": self.options.get('PASSWORD', None),
        }

        if host == "unix":
            kwargs.update({'path': port, 'connection_class': UnixDomainSocketConnection})
        else:
            kwargs.update({'host': host, 'port': port, 'connection_class': Connection})

        if 'SOCKET_TIMEOUT' in self.options:
            kwargs['socket_timeout'] = int(self.options['SOCKET_TIMEOUT'])

        return Redis(connection_pool=self.get_or_create_connection_pool(kwargs))

    def get_parser_cls(self):
        cls = self.options.get('PARSER_CLASS', None)
        if cls is None:
            return DefaultParser
        return util.load_class(cls)

    def get_or_create_connection_pool(self, params):
        """
        Given a connection parameters and return a new
        or cached connection pool for them.

        Reimplement this method if you want distinct
        connection pool instance caching behavior.
        """
        key = frozenset((k, repr(v)) for (k, v) in params.items())
        if key not in self._pools:
            self._pools[key] = self.get_connection_pool(params)
        return self._pools[key]

    def get_connection_pool(self, params):
        """
        Given a connection parameters, return a new
        connection pool for them.

        Overwrite this method if you want a custom
        behavior on creating connection pool.
        """
        cp_params = dict(params)
        cp_params.update(self.pool_cls_kwargs)
        return self.pool_cls(**cp_params)


def get_connection_factory(path=None, options=None):
    if path is None:
        path = getattr(settings, "DJANGO_REDIS_CONNECTION_FACTORY",
                       "redis_cache.pool.ConnectionFactory")

    cls = util.load_class(path)
    return cls(options or {})

