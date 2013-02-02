# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.core.exceptions import ImproperlyConfigured

try:
    from django.utils.encoding import smart_bytes
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes

from django.utils.datastructures import SortedDict
from django.utils import importlib
from django.conf import settings

try:
    import cPickle as pickle
except ImportError:
    import pickle

from collections import defaultdict
import functools
import re

from redis import Redis
from redis.exceptions import ConnectionError
from redis.connection import DefaultParser
from redis.connection import UnixDomainSocketConnection, Connection

from ..util import CacheKey, load_class
from ..hash_ring import HashRing
from ..exceptions import ConnectionInterrumped
from ..pool import get_or_create_connection_pool

from .default import DefaultClient


class ShardClient(DefaultClient):
    _findhash = re.compile('.*\{(.*)\}.*', re.I)

    def __init__(self, *args, **kwargs):
        super(ShardClient, self).__init__(*args, **kwargs)

        if not isinstance(self._server, (list, tuple)):
            self._server = [self._server]

        self._ring = HashRing(self._server)
        self._serverdict = self.connect()

    @property
    def client(self):
        raise NotImplementedError

    def connect(self):
        connection_dict = {}
        for name in self._server:
            host, port, db = self.parse_connection_string(name)
            connection_dict[name] = self._connect(host, port, db)

        return connection_dict

    def get_server_name(self, _key):
        key = str(_key)
        g = self._findhash.match(key)
        if g is not None and len(g.groups()) > 0:
            key = g.groups()[0]
        name = self._ring.get_node(key)
        return name

    def get_server(self, key):
        name = self.get_server_name(key)
        return self._serverdict[name]

    def add(self,  key, value, timeout=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .add(key=key, value=value, version=version, client=client)

    def get(self,  key, default=None, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .get(key=key, default=default, version=version, client=client)

    def get_many(self, keys, version=None):
        if not keys:
            return {}

        recovered_data = SortedDict()

        new_keys = [self.make_key(key, version=version) for key in keys]
        map_keys = dict(zip(new_keys, keys))

        for key in new_keys:
            client = self.get_server(key)
            value = self.get(key=key, version=version, client=client)

            if value is None:
                continue

            recovered_data[map_keys[key]] = value
        return recovered_data

    def set(self, key, value, timeout=None, version=None, client=None, nx=False):
        """
        Persist a value to the cache, and set an optional expiration time.
        """
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self).set(
                        key=key, value=value, timeout=timeout,
                        version=version, client=client, nx=nx)

    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        for key, value in data.items():
            self.set(key, value, timeout, version=version)

    def has_key(self, key, version=None, client=None):
        """
        Test if key exists.
        """

        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        key = self.make_key(key, version=version)
        try:
            return client.exists(key)
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete(self, key, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self).delete(key=key, version=version, client=client)

    def delete_many(self, keys, version=None):
        """
        Remove multiple keys at once.
        """
        for key in map(lambda key: self.make_key(key, version=version), keys):
            client = self.get_server(key)
            self.delete(key, client=client)

    def incr_version(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .incr_version(key=key, delta=delta, version=version, client=client)

    def incr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .incr(key=key, delta=delta, version=version, client=client)

    def decr(self, key, delta=1, version=None, client=None):
        if client is None:
            key = self.make_key(key, version=version)
            client = self.get_server(key)

        return super(ShardClient, self)\
            .decr(key=key, delta=delta, version=version, client=client)


    def keys(self, search):
        pattern = self.make_key(search)

        keys = []
        for server, connection in self._serverdict.items():
            keys.extend(connection.keys(pattern))

        try:
            encoding_map = map(lambda x:  x.decode('utf-8'), keys)
            return list(map(lambda x: x.split(":", 2)[2], encoding_map))
        except ConnectionError:
            raise ConnectionInterrumped(connection=client)

    def delete_pattern(self, pattern, version=None):
        """
        Remove all keys matching pattern.
        """

        pattern = self.make_key(pattern, version=version)

        keys = []
        for server, connection in self._serverdict.items():
            keys.extend(connection.keys(pattern))

        if keys:
            for server, connection in self._serverdict.items():
                connection.delete(*keys)

    def close(self, **kwargs):
        if getattr(settings, "DJANGO_REDIS_CLOSE_CONNECTION", False):
            for client in self._serverdict.values():
                for c in client.connection_pool._available_connections:
                    c.disconnect()
