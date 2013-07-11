# -*- coding: utf-8 -*-
_connection_pools = {}


def get_or_create_connection_pool(pool_cls, **params):
    global _connection_pools

    key = str(params)
    if key not in _connection_pools:
        _connection_pools[key] = pool_cls(**params)
    return _connection_pools[key]


__all__ = ['get_or_create_connection_pool']
