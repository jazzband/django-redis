# -*- coding: utf-8 -*-

from django.conf import settings
try:
    from django.utils.timezone import now as datetime_now
    assert datetime_now
except ImportError:
    import datetime
    datetime_now = datetime.datetime.now
from redis.sentinel import Sentinel
from .default import DefaultClient
from ..exceptions import ConnectionInterrumped
import functools


class SentinelClient(DefaultClient):
    def __init__(self, server, params, backend):
        super(SentinelClient, self).__init__(server, params, backend)

    def parse_connection_string(self, constring):
        try:
            connection_params = constring.split('/')
            master_name = connection_params[0]
            servers = connection_params[1:-1]
            sentinel_hosts = [tuple(host_port.split(':')) for host_port in self._server]
            db = connection_params[-1]
        except (ValueError, TypeError):
            raise ImproperlyConfigured("Incorrect format '%s'" % (constring))
        
        return master_name, servers, db

    def get_client(self, write=True):
        if self._clients[0] is None:
            self._clients[0] = self.connect(0, write)

        return self._clients[0]

    def connect(self, index=0, write=True):
        """
        Creates a redis connection with connection pool.
        """
        master_name, sentinel_hosts, db = self.parse_connection_string(self._server[index])

        sentinel = Sentinel(sentinel_hosts, socket_timeout=self._options.get('SENTINEL_TIMEOUT', 1))

        if write:
            host, port = sentinel.discover_master(master_name)
        else:
            host, port = random.choice([sentinel.discover_master(master_name)] + sentinel.discover_slaves(master_name))

        kwargs = {
            "db": db,
            "parser_class": self.parser_class,
            "password": self._options.get('PASSWORD', None),
        }

        kwargs.update({'host': host, 'port': port, 'connection_class': Connection})

        if 'SOCKET_TIMEOUT' in self._options:
            kwargs.update({'socket_timeout': int(self._options['SOCKET_TIMEOUT'])})

        kwargs.update(self._pool_cls_kwargs)

        connection_pool = get_or_create_connection_pool(self._pool_cls, **kwargs)
        connection = Redis(connection_pool=connection_pool)
        return connection
