# -*- coding: utf-8 -*-

from django.utils.encoding import smart_unicode, smart_str

class CacheKey(object):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def __init__(self, key):
        self._key = key

    def __eq__(self, other):
        return self._key == other

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return self.__unicode__()

    def __unicode__(self):
        return smart_str(self._key)

    def original_key(self):
        _, key = self._key.rsplit(":", 1)
        return key


class Singleton(type):
    """ Singleton metaclass. """

    def __init__(cls, name, bases, dct):
        cls.__instance = None
        type.__init__(cls, name, bases, dct)
 
    def __call__(cls, *args, **kw):
        if cls.__instance is None:
            cls.__instance = type.__call__(cls, *args,**kw)
        return cls.__instance


from collections import defaultdict
from redis import ConnectionPool as RedisConnectionPool
from redis.connection import UnixDomainSocketConnection, Connection
from redis.connection import DefaultParser


class ConnectionPoolHandler(object):
    __metaclass__ = Singleton
    pools = {}

    def key_for_kwargs(self, kwargs):
        return ":".join([str(v) for v in kwargs.values()])

    def connection_pool(self, parser_class=DefaultParser, **kwargs):
        pool_key = self.key_for_kwargs(kwargs)

        if pool_key in self.pools:
            return self.pools[pool_key]

        connection_class = kwargs['unix_socket_path'] \
            and UnixDomainSocketConnection or Connection
        
        params = {
            'connection_class': connection_class,
            'parser_class': parser_class,
            'db': kwargs['db'],
            'password': kwargs['password']
        }

        # port 6379
        if kwargs['unix_socket_path']:
            params['path'] = kwargs['unix_socket_path']
        else:
            params['host'], params['port'] = kwargs['host'], kwargs['port']
        
        connection_pool = RedisConnectionPool(**params)
        self.pools[pool_key] = connection_pool
        return connection_pool
