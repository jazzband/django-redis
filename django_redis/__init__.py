# -*- coding: utf-8 -*-

VERSION = (4, 4, 3)
__version__ = '.'.join(map(str, VERSION))


def get_redis_connection(alias='default', write=True):
    """
    Helper used for obtain a raw redis client.
    """

    try:
        from django.core.cache import caches
    except ImportError:
        # Django <1.7
        from django.core.cache import get_cache
    else:
        def get_cache(alias):
            return caches[alias]

    cache = get_cache(alias)

    if not hasattr(cache, "client"):
        raise NotImplementedError("This backend does not supports this feature")

    if not hasattr(cache.client, "get_client"):
        raise NotImplementedError("This backend does not supports this feature")

    return cache.client.get_client(write)
