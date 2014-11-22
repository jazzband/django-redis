# -*- coding: utf-8 -*-

import functools
import random

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from redis import Redis
from redis.sentinel import Sentinel
from redis.connection import Connection

from .default import DefaultClient
from ..exceptions import ConnectionInterrupted


class SentinelClient(DefaultClient):
    def __init__(self, server, params, backend):
        """
        Slightly different logic than connection to multiple Redis servers. Reserve only one write and read
        descriptors, as they will be closed on exit anyway.
        """
        super(SentinelClient, self).__init__(server, params, backend)
        self._client_write = None
        self._client_read = None
        self._connection_string = server

    def parse_connection_string(self, constring):
        """
        Parse connection string in format:
            master_name/sentinel_server:port,sentinel_server:port/db_id
        Returns master name, list of tuples with pair (host, port) and db_id
        """
        try:
            connection_params = constring.split('/')
            master_name = connection_params[0]
            servers = [host_port.split(':') for host_port in connection_params[1].split(',')]
            sentinel_hosts = [(host, int(port)) for host, port in servers]
            db = connection_params[2]
        except (ValueError, TypeError):
            raise ImproperlyConfigured("Incorrect format '%s'" % (constring))

        return master_name, sentinel_hosts, db

    def get_client(self, write=True):
        if write:
            if self._client_write is None:
                self._client_write = self.connect(0, write)

            return self._client_write

        if self._client_read is None:
            self._client_read = self.connect(0, write)

        return self._client_read

    def connect(self, index=0, write=True):
        """
        Creates a redis connection with connection pool.
        """
        master_name, sentinel_hosts, db = self.parse_connection_string(self._connection_string)

        sentinel_timeout = self._options.get('SENTINEL_TIMEOUT', 1)
        sentinel = Sentinel(sentinel_hosts, socket_timeout=sentinel_timeout)

        if write:
            host, port = sentinel.discover_master(master_name)
        else:
            host, port = random.choice([sentinel.discover_master(master_name)] + sentinel.discover_slaves(master_name))

        return self.connection_factory.connect(host, port, db)

    def close(self, **kwargs):
        """
        Closing old connections, as master may change in time of inactivity.
        """

        if self._client_read:
            for c in self._client_read.connection_pool._available_connections:
                c.disconnect()

        if self._client_write:
            for c in self._client_write.connection_pool._available_connections:
                c.disconnect()

        del(self._client_write)
        del(self._client_read)
        self._client_write = None
        self._client_read = None
