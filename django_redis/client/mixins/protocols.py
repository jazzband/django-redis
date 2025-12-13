from typing import Any, Optional, Protocol, Union

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
        version: Optional[int] = None,
        prefix: Optional[str] = None,
    ) -> KeyT:
        """Create a cache key with optional version and prefix."""
        ...

    def encode(self, value: Any) -> Union[bytes, int]:
        """Encode a value for storage in Redis."""
        ...

    def decode(self, value: Union[bytes, int]) -> Any:
        """Decode a value retrieved from Redis."""
        ...

    def get_client(self, write: bool = False) -> Redis:
        """Get a Redis client instance for read or write operations."""
        ...

    def _has_compression_enabled(self) -> bool:
        """Check if compression is enabled for this client."""
        ...

    def _decode_iterable_result(
        self,
        result: Any,
        covert_to_set: bool = True,
    ) -> Union[list[Any], None, Any]:
        """Decode an iterable result from Redis."""
        ...
