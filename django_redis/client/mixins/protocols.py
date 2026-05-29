from typing import Any, Protocol

from redis import Redis
from redis.typing import KeyT


class ClientProtocol(Protocol):
    """
    Protocol for client methods required by mixins.

    Any class using django-redis mixins must implement these methods.
    """

    def make_key(
        self,
        key: KeyT,
        version: int | None = None,
        prefix: str | None = None,
    ) -> KeyT:
        """Create a cache key with optional version and prefix."""
        ...

    def encode(self, value: Any) -> bytes | int:
        """Encode a value for storage in Redis."""
        ...

    def decode(self, value: bytes | int) -> Any:
        """Decode a value retrieved from Redis."""
        ...

    def get_client(self, write: bool = False) -> Redis:
        """Get a Redis client instance for read or write operations."""
        ...
