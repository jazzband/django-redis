from typing import Any, Optional, Union

from redis import Redis
from redis.typing import KeyT

from django_redis.client.mixins.protocols import ClientProtocol


class ListMixin(ClientProtocol):
    """Mixin providing Redis list operations."""

    def lpush(
        self,
        key: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Insert values at head of list."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.lpush(key, *encoded_values))

    def rpush(
        self,
        key: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Insert values at tail of list."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.rpush(key, *encoded_values))

    def lpop(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[Any, list[Any], None]:
        """Remove and return element(s) from head of list."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        result = client.lpop(key, count=count)

        if result is None:
            return None
        if isinstance(result, list):
            return [self.decode(item) for item in result]
        return self.decode(result)

    def rpop(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[Any, list[Any], None]:
        """Remove and return element(s) from tail of list."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        result = client.rpop(key, count=count)

        if result is None:
            return None
        if isinstance(result, list):
            return [self.decode(item) for item in result]
        return self.decode(result)

    def lrange(
        self,
        key: KeyT,
        start: int,
        end: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> list[Any]:
        """Return range of elements from list."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.lrange(key, start, end)
        return [self.decode(item) for item in result]

    def lindex(
        self,
        key: KeyT,
        index: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[Any]:
        """Return element at index in list."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.lindex(key, index)
        if result is None:
            return None
        return self.decode(result)

    def llen(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Return length of list."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return int(client.llen(key))

    def lrem(
        self,
        key: KeyT,
        count: int,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove elements from list equal to value."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_value = self.encode(value)
        return int(client.lrem(key, count, encoded_value))

    def ltrim(
        self,
        key: KeyT,
        start: int,
        end: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Trim list to specified range."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        return bool(client.ltrim(key, start, end))

    def lset(
        self,
        key: KeyT,
        index: int,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Set element at index in list."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_value = self.encode(value)
        return bool(client.lset(key, index, encoded_value))
