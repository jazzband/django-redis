from typing import Any, Optional, Union

from redis import Redis
from redis.typing import KeyT

from django_redis.client.mixins.protocols import ClientProtocol


class SortedSetMixin(ClientProtocol):
    """Mixin providing Redis sorted set (ZSET) operations."""

    def zadd(
        self,
        name: KeyT,
        mapping: dict[Any, float],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False,
        gt: bool = False,
        lt: bool = False,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Add members with scores to sorted set."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        # Encode members but NOT scores (scores must remain as floats)
        encoded_mapping = {
            self.encode(member): score for member, score in mapping.items()
        }

        return int(
            client.zadd(
                name,
                encoded_mapping,  # type: ignore[arg-type]
                nx=nx,
                xx=xx,
                ch=ch,
                incr=incr,
                gt=gt,
                lt=lt,
            ),
        )

    def zcard(
        self,
        name: KeyT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Get the number of members in sorted set."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        return int(client.zcard(name))

    def zcount(
        self,
        name: KeyT,
        min: Union[float, str],
        max: Union[float, str],
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Count members in sorted set with scores between min and max."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        return int(client.zcount(name, min, max))

    def zincrby(
        self,
        name: KeyT,
        amount: float,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> float:
        """Increment the score of member in sorted set by amount."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        value = self.encode(value)
        return float(client.zincrby(name, amount, value))

    def zpopmax(
        self,
        name: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[tuple[Any, float]], tuple[Any, float], None]:
        """Remove and return members with highest scores."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        result = client.zpopmax(name, count)

        if not result:
            return None if count is None else []

        decoded = [(self.decode(member), score) for member, score in result]

        if count is None:
            return decoded[0] if decoded else None

        return decoded

    def zpopmin(
        self,
        name: KeyT,
        count: Optional[int] = None,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[tuple[Any, float]], tuple[Any, float], None]:
        """Remove and return members with lowest scores."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        result = client.zpopmin(name, count)

        if not result:
            return None if count is None else []

        decoded = [(self.decode(member), score) for member, score in result]

        if count is None:
            return decoded[0] if decoded else None

        return decoded

    def zrange(
        self,
        name: KeyT,
        start: int,
        end: int,
        desc: bool = False,
        withscores: bool = False,
        score_cast_func: type = float,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[Any], list[tuple[Any, float]]]:
        """Return members in sorted set by index range."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.zrange(
            name,
            start,
            end,
            desc=desc,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [(self.decode(member), score) for member, score in result]

        return [self.decode(member) for member in result]

    def zrangebyscore(
        self,
        name: KeyT,
        min: Union[float, str],
        max: Union[float, str],
        start: Optional[int] = None,
        num: Optional[int] = None,
        withscores: bool = False,
        score_cast_func: type = float,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[Any], list[tuple[Any, float]]]:
        """Return members in sorted set by score range."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.zrangebyscore(
            name,
            min,
            max,
            start=start,
            num=num,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [(self.decode(member), score) for member, score in result]

        return [self.decode(member) for member in result]

    def zrank(
        self,
        name: KeyT,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[int]:
        """Get the rank (index) of member in sorted set, ordered low to high."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        value = self.encode(value)
        rank = client.zrank(name, value)

        return int(rank) if rank is not None else None

    def zrem(
        self,
        name: KeyT,
        *values: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove members from sorted set."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        encoded_values = [self.encode(value) for value in values]
        return int(client.zrem(name, *encoded_values))

    def zremrangebyscore(
        self,
        name: KeyT,
        min: Union[float, str],
        max: Union[float, str],
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> int:
        """Remove members from sorted set with scores between min and max."""
        if client is None:
            client = self.get_client(write=True)

        name = self.make_key(name, version=version)
        return int(client.zremrangebyscore(name, min, max))

    def zrevrange(
        self,
        name: KeyT,
        start: int,
        end: int,
        withscores: bool = False,
        score_cast_func: type = float,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[Any], list[tuple[Any, float]]]:
        """Return members in sorted set by index range, ordered high to low."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.zrevrange(
            name,
            start,
            end,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [(self.decode(member), score) for member, score in result]

        return [self.decode(member) for member in result]

    def zrevrangebyscore(
        self,
        name: KeyT,
        max: Union[float, str],
        min: Union[float, str],
        start: Optional[int] = None,
        num: Optional[int] = None,
        withscores: bool = False,
        score_cast_func: type = float,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Union[list[Any], list[tuple[Any, float]]]:
        """Return members in sorted set by score range, ordered high to low."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        result = client.zrevrangebyscore(
            name,
            max,
            min,
            start=start,
            num=num,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [(self.decode(member), score) for member, score in result]

        return [self.decode(member) for member in result]

    def zscore(
        self,
        name: KeyT,
        value: Any,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
    ) -> Optional[float]:
        """Get the score of member in sorted set."""
        if client is None:
            client = self.get_client(write=False)

        name = self.make_key(name, version=version)
        value = self.encode(value)
        score = client.zscore(name, value)

        return float(score) if score is not None else None
