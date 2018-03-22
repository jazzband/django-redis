# -*- coding: utf-8 -*-

from django.core.cache import caches

def get_redis_connection(alias='default', write=True):
    """
    Helper used for obtain a raw redis client.
    """

    cache = caches[alias]
    if not hasattr(cache.client, 'get_client'):
        raise NotImplementedError("This backend does not supports this feature")

    return cache.client.get_client(write)
