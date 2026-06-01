from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, overload

if TYPE_CHECKING:
    from redis import Redis

    from django_redis.util import CacheKey


class ClientProtocol(Protocol):
    """
    Protocol for client methods required by mixins.

    Any class using django-redis mixins must implement these methods.
    """

    def make_key(
        self,
        key: str,
        version: int | None = None,
        prefix: str | None = None,
    ) -> CacheKey:
        """Create a cache key with optional version and prefix."""
        ...

    @overload
    def encode(self, value: Any, *, allow_int: Literal[False]) -> bytes: ...
    @overload
    def encode(self, value: Any, *, allow_int: bool = ...) -> bytes | int: ...
    def encode(self, value: Any, *, allow_int: bool = True) -> bytes | int:
        """Encode a value for storage in Redis."""
        ...

    def decode(self, value: bytes | int | str) -> Any:
        """Decode a value retrieved from Redis."""
        ...

    def get_client(self, write: bool = False) -> Redis:
        """Get a Redis client instance for read or write operations."""
        ...
