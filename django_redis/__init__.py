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

    .. note::
        The returned client is a raw Redis connection that does not apply
        the ``KEY_PREFIX`` configured in your Django cache settings.  To
        work with prefixed keys use :func:`get_key_prefix` to retrieve the
        configured prefix, or use the Django cache API which handles
        prefixing automatically.
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


def get_key_prefix(alias: str = "default") -> str:
    """
    Return the ``KEY_PREFIX`` configured for the given cache alias.

    This is useful when you need to work with the raw Redis connection
    returned by :func:`get_redis_connection` and want to manually apply
    the same prefix that the Django cache backend uses::

        from django_redis import get_redis_connection, get_key_prefix

        conn = get_redis_connection()
        prefix = get_key_prefix()
        conn.set(f"{prefix}:my_key", "value")

    :param alias: The cache alias (default ``"default"``).
    :returns: The configured key prefix string, or an empty string.
    """
    try:
        from django.core.cache import caches

        return cast("Any", caches[alias]).key_prefix
    except Exception:
        return ""
