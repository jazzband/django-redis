from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from redis import Redis

VERSION = (7, 0, 0)
__version__ = ".".join(map(str, VERSION))


def get_redis_connection(alias: str = "default", write: bool = True) -> Redis:
    """
    Helper used for obtaining a raw redis client.
    """

    try:
        from django.core.cache import caches

        get_client = cast(
            "Callable[[bool], Redis]",
            cast("Any", caches[alias]).client.get_client,
        )
    except AttributeError:
        message = "This backend does not support this feature"
        raise NotImplementedError(message) from None

    return get_client(write)
