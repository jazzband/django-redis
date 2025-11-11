import builtins
from collections.abc import Iterator
from typing import Any, Optional, Union

from redis import Redis
from redis.typing import KeyT

from django_redis.client.mixins.protocols import ClientProtocol


class SetMixin(ClientProtocol):
    """Mixin providing Redis set operations."""

    def sadd(
        self,
        key: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Add one or more members to a set."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.sadd(key, *encoded_values))

    def scard(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Get the number of members in a set."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return int(client.scard(key))

    def sdiff(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        """Return the difference of multiple sets."""
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sdiff(*nkeys)}  # type: ignore[arg-type]

    def sdiffstore(
        self,
        dest: KeyT,
        *keys: KeyT,
        version_dest: Optional[int] = None,
        version_keys: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Store the difference of multiple sets in a destination key."""
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version_dest)
        nkeys = [self.make_key(key, version=version_keys) for key in keys]
        return int(client.sdiffstore(dest, *nkeys))

    def sinter(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        """Return the intersection of multiple sets."""
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sinter(*nkeys)}  # type: ignore[arg-type]

    def sinterstore(
        self,
        dest: KeyT,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Store the intersection of multiple sets in a destination key."""
        if client is None:
            client = self.get_client(write=True)

        dest = self.make_key(dest, version=version)
        nkeys = [self.make_key(key, version=version) for key in keys]
        return int(client.sinterstore(dest, *nkeys))

    def sismember(
        self,
        key: KeyT,
        member: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Check if member is in set."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        member = self.encode(member)
        return bool(client.sismember(key, member))

    def smembers(
        self,
        key: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        """Get all members in a set."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return {self.decode(value) for value in client.smembers(key)}

    def smismember(
        self,
        key: KeyT,
        *members,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> list[bool]:
        """Check if multiple members are in set."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        encoded_members = [self.encode(member) for member in members]

        return [bool(value) for value in client.smismember(key, *encoded_members)]

    def smove(
        self,
        source: KeyT,
        destination: KeyT,
        member: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> bool:
        """Move member from source set to destination set."""
        if client is None:
            client = self.get_client(write=True)

        source = self.make_key(source, version=version)
        destination = self.make_key(destination)
        member = self.encode(member)
        return bool(client.smove(source, destination, member))

    def spop(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[builtins.set, Any]:
        """Remove and return random members from set."""
        if client is None:
            client = self.get_client(write=True)

        nkey = self.make_key(key, version=version)
        result = client.spop(nkey, count)
        return self._decode_iterable_result(result)

    def srandmember(
        self,
        key: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list, Any]:
        """Get random members from set without removing them."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.srandmember(key, count)
        return self._decode_iterable_result(result, covert_to_set=False)

    def srem(
        self,
        key: KeyT,
        *members: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove one or more members from a set."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        nmembers = [self.encode(member) for member in members]
        return int(client.srem(key, *nmembers))

    def sscan(
        self,
        key: KeyT,
        match: Optional[str] = None,
        count: Optional[int] = 10,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        """Incrementally iterate over members in a set."""
        if self._has_compression_enabled() and match:
            err_msg = "Using match with compression is not supported."
            raise ValueError(err_msg)

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)

        cursor, result = client.sscan(
            key,
            match=self.encode(match) if match else None,  # type: ignore[arg-type]
            count=count,
        )
        return {self.decode(value) for value in result}

    def sscan_iter(
        self,
        key: KeyT,
        match: Optional[str] = None,
        count: Optional[int] = 10,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Iterator[Any]:
        """Incrementally iterate over members in a set (generator)."""
        if self._has_compression_enabled() and match:
            err_msg = "Using match with compression is not supported."
            raise ValueError(err_msg)

        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        for value in client.sscan_iter(
            key,
            match=self.encode(match) if match else None,  # type: ignore[arg-type]
            count=count,
        ):
            yield self.decode(value)

    def sunion(
        self,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> builtins.set[Any]:
        """Return the union of multiple sets."""
        if client is None:
            client = self.get_client(write=False)

        nkeys = [self.make_key(key, version=version) for key in keys]
        return {self.decode(value) for value in client.sunion(*nkeys)}  # type: ignore[arg-type]

    def sunionstore(
        self,
        destination: Any,
        *keys: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Store the union of multiple sets in a destination key."""
        if client is None:
            client = self.get_client(write=True)

        destination = self.make_key(destination, version=version)
        encoded_keys = [self.make_key(key, version=version) for key in keys]
        return int(client.sunionstore(destination, *encoded_keys))
