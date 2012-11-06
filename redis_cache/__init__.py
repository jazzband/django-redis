# -*- coding: utf-8 -*-

from django.core.cache import get_cache

def get_redis_connection(alias='default'):
    """
    Helper used for obtain a raw redis client.
    """

    cache = get_cache(alias)
    if not hasattr(cache, 'raw_client'):
        raise NotImplementedError("This backend does not supports this feature")

    return cache.raw_client
