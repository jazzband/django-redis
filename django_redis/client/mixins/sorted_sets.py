from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django_redis.client.mixins.protocols import ClientProtocol

if TYPE_CHECKING:
    from redis import Redis
    from redis.typing import ZSetScoredMembers


class SortedSetMixin(ClientProtocol):
    """Mixin providing Redis sorted set (ZSET) operations."""

    def zadd(
        self,
        key: str,
        mapping: dict[Any, float],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False,
        gt: bool = False,
        lt: bool = False,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int | float | None:
        """Add members with scores to sorted set."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        # Encode members but NOT scores (scores must remain as floats)
        encoded_mapping = {
            self.encode(member, allow_int=False): score
            for member, score in mapping.items()
        }

        return client.zadd(
            key,
            encoded_mapping,
            nx=nx,
            xx=xx,
            ch=ch,
            incr=incr,
            gt=gt,
            lt=lt,
        )

    def zcard(
        self,
        key: str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """Get the number of members in sorted set."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return client.zcard(key)

    def zcount(
        self,
        key: str,
        min: float | str,
        max: float | str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """Count members in sorted set with scores between min and max."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        return client.zcount(key, min, max)

    def zincrby(
        self,
        key: str,
        amount: float,
        value: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> float | None:
        """Increment the score of member in sorted set by amount."""
        if client is None:
            client = self.get_client(write=True)

        return client.zincrby(
            self.make_key(key, version=version),
            amount,
            self.encode(value, allow_int=False),
        )

    def zpopmax(
        self,
        key: str,
        count: int | None = None,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[tuple[Any, float]] | tuple[Any, float] | None:
        """Remove and return members with highest scores."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        result = cast("ZSetScoredMembers", client.zpopmax(key, count))

        if not result:
            return None if count is None else []

        decoded = [(self.decode(member), score) for member, score in result]

        if count is None:
            return decoded[0] if decoded else None

        return decoded

    def zpopmin(
        self,
        key: str,
        count: int | None = None,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[tuple[Any, float]] | tuple[Any, float] | None:
        """Remove and return members with lowest scores."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        result = cast("ZSetScoredMembers", client.zpopmin(key, count))

        if not result:
            return None if count is None else []

        decoded = [(self.decode(member), score) for member, score in result]

        if count is None:
            return decoded[0] if decoded else None

        return decoded

    def zrange(
        self,
        key: str,
        start: int,
        end: int,
        desc: bool = False,
        withscores: bool = False,
        score_cast_func: type = float,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[Any] | list[tuple[Any, float]]:
        """Return members in sorted set by index range."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.zrange(
            key,
            start,
            end,
            desc=desc,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [
                (self.decode(member), score)
                for member, score in cast("ZSetScoredMembers", result)
            ]

        return [self.decode(member) for member in cast("list[bytes | str]", result)]

    def zrangebyscore(
        self,
        key: str,
        min: float | str,
        max: float | str,
        start: int | None = None,
        num: int | None = None,
        withscores: bool = False,
        score_cast_func: type = float,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[Any] | list[tuple[Any, float]]:
        """Return members in sorted set by score range."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.zrangebyscore(
            key,
            min,
            max,
            start=start,
            num=num,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [
                (self.decode(member), score)
                for member, score in cast("ZSetScoredMembers", result)
            ]

        return [self.decode(member) for member in cast("list[bytes | str]", result)]

    def zrank(
        self,
        key: str,
        value: Any,
        withscore: bool = False,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int | list[Any] | None:
        """Get the rank (index) of member in sorted set, ordered low to high."""
        if client is None:
            client = self.get_client(write=False)

        return client.zrank(
            self.make_key(key, version=version),
            self.encode(value, allow_int=False),
            withscore=withscore,
        )

    def zrem(
        self,
        key: str,
        *values: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """Remove members from sorted set."""
        if client is None:
            client = self.get_client(write=True)

        return client.zrem(
            self.make_key(key, version=version),
            *[self.encode(value, allow_int=False) for value in values],
        )

    def zremrangebyscore(
        self,
        key: str,
        min: float | str,
        max: float | str,
        version: int | None = None,
        client: Redis | None = None,
    ) -> int:
        """Remove members from sorted set with scores between min and max."""
        if client is None:
            client = self.get_client(write=True)

        key = self.make_key(key, version=version)
        return client.zremrangebyscore(key, min, max)

    def zrevrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False,
        score_cast_func: type = float,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[Any] | list[tuple[Any, float]]:
        """Return members in sorted set by index range, ordered high to low."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.zrevrange(
            key,
            start,
            end,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [
                (self.decode(member), score)
                for member, score in cast("ZSetScoredMembers", result)
            ]

        return [self.decode(member) for member in cast("list[bytes | str]", result)]

    def zrevrangebyscore(
        self,
        key: str,
        max: float | str,
        min: float | str,
        start: int | None = None,
        num: int | None = None,
        withscores: bool = False,
        score_cast_func: type = float,
        version: int | None = None,
        client: Redis | None = None,
    ) -> list[Any] | list[tuple[Any, float]]:
        """Return members in sorted set by score range, ordered high to low."""
        if client is None:
            client = self.get_client(write=False)

        key = self.make_key(key, version=version)
        result = client.zrevrangebyscore(
            key,
            max,
            min,
            start=start,
            num=num,
            withscores=withscores,
            score_cast_func=score_cast_func,
        )

        if withscores:
            return [
                (self.decode(member), score)
                for member, score in cast("ZSetScoredMembers", result)
            ]

        return [self.decode(member) for member in cast("list[bytes | str]", result)]

    def zscore(
        self,
        key: str,
        value: Any,
        version: int | None = None,
        client: Redis | None = None,
    ) -> float | None:
        """Get the score of member in sorted set."""
        if client is None:
            client = self.get_client(write=False)

        return client.zscore(
            self.make_key(key, version=version),
            self.encode(value, allow_int=False),
        )
