from typing import Any, Optional

from redis import Redis
from redis.typing import EncodableT, KeyT

from django_redis.client.mixins.protocols import ClientProtocol
from django_redis.exceptions import ConnectionInterrupted


class HashMixin(ClientProtocol):
    """Mixin providing Redis hash operations."""

    def hset(
        self,
        name: str,
        key: KeyT,
        value: EncodableT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Set the value of hash name at key to value."""
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        nvalue = self.encode(value)
        return int(client.hset(name, nkey, nvalue))

    def hdel(
        self,
        name: str,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove keys from hash name."""
        if client is None:
            client = self.get_client(write=True)
        nkey = self.make_key(key, version=version)
        return int(client.hdel(name, nkey))

    def hlen(
        self,
        name: str,
        client: Optional[Redis] = None,
    ) -> int:
        """Return the number of items in hash name."""
        if client is None:
            client = self.get_client(write=False)
        return int(client.hlen(name))

    def hkeys(
        self,
        name: str,
        client: Optional[Redis] = None,
    ) -> list[Any]:
        """Return a list of keys in hash name."""
        if client is None:
            client = self.get_client(write=False)
        try:
            return [self.reverse_key(k.decode()) for k in client.hkeys(name)]
        except Exception as e:
            raise ConnectionInterrupted(connection=client) from e

    def hexists(
        self,
        name: str,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Return True if key exists in hash name, else False."""
        if client is None:
            client = self.get_client(write=False)
        nkey = self.make_key(key, version=version)
        return bool(client.hexists(name, nkey))
