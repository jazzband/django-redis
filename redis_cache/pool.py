# -*- coding: utf-8 -*-

from redis import ConnectionPool

_connection_pools = {}


def get_or_create_connection_pool(**params):
    global _connection_pools

    key = str(params)
    if key not in _connection_pools:
        _connection_pools[key] = ConnectionPool(**params)
    return _connection_pools[key]


__all__ = ['get_or_create_connection_pool']
