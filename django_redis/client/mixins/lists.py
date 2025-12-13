from typing import Any, Optional, Union

from redis import Redis
from redis.typing import KeyT

from django_redis.client.mixins.protocols import ClientProtocol


class ListMixin(ClientProtocol):
    """Mixin providing Redis list operations."""

    def lpush(
        self,
        name: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Insert values at head of list."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.lpush(name, *encoded_values))

    def rpush(
        self,
        name: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Insert values at tail of list."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.rpush(name, *encoded_values))

    def lpop(
        self,
        name: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[Any, list[Any], None]:
        """Remove and return element(s) from head of list."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        result = client.lpop(name, count=count)

        if result is None:
            return None
        if isinstance(result, list):
            return [self.decode(item) for item in result]
        return self.decode(result)

    def rpop(
        self,
        name: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[Any, list[Any], None]:
        """Remove and return element(s) from tail of list."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        result = client.rpop(name, count=count)

        if result is None:
            return None
        if isinstance(result, list):
            return [self.decode(item) for item in result]
        return self.decode(result)

    def lrange(
        self,
        name: KeyT,
        start: int,
        end: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> list[Any]:
        """Return range of elements from list."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.lrange(name, start, end)
        return [self.decode(item) for item in result]

    def lindex(
        self,
        name: KeyT,
        index: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[Any]:
        """Return element at index in list."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.lindex(name, index)
        if result is None:
            return None
        return self.decode(result)

    def llen(
        self,
        name: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Return length of list."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        return int(client.llen(name))

    def lrem(
        self,
        name: KeyT,
        count: int,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove elements from list equal to value."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        encoded_value = self.encode(value)
        return int(client.lrem(name, count, encoded_value))

    def ltrim(
        self,
        name: KeyT,
        start: int,
        end: int,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Trim list to specified range."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        return bool(client.ltrim(name, start, end))

    def lset(
        self,
        name: KeyT,
        index: int,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Set element at index in list."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        encoded_value = self.encode(value)
        return bool(client.lset(name, index, encoded_value))
