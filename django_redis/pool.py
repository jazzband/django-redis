from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Protocol, cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from redis.connection import DefaultParser, to_bool
from redis.sentinel import Sentinel

if sys.version_info < (3, 13):
    from typing_extensions import TypeVar
else:
    from typing import TypeVar

if TYPE_CHECKING:
    from redis import ConnectionPool, Redis
    from redis._parsers import BaseParser, _RESP2Parser

ConnectionPoolType = TypeVar(
    "ConnectionPoolType",
    bound="ConnectionPool",
    default="ConnectionPool",
)
ConnectionPoolType_co = TypeVar(
    "ConnectionPoolType_co",
    bound="ConnectionPool",
    covariant=True,
    default="ConnectionPool",
)
RedisParserType = TypeVar("RedisParserType", bound="BaseParser", default="_RESP2Parser")
RedisParserType_co = TypeVar(
    "RedisParserType_co",
    bound="BaseParser",
    covariant=True,
    default="_RESP2Parser",
)
RedisType = TypeVar("RedisType", bound="Redis", default="Redis")


class ConnectionFactoryProtocol(
    Protocol[RedisType, ConnectionPoolType_co, RedisParserType_co],
):
    def __init__(self, options: dict[str, Any]) -> None: ...
    def make_connection_params(self, url: str) -> dict[str, Any]: ...
    def connect(self, url: str) -> RedisType: ...
    def disconnect(self, connection: RedisType) -> None: ...
    def get_connection(self, params: dict[str, Any]) -> RedisType: ...
    def get_parser_cls(self) -> type[RedisParserType_co]: ...
    def get_or_create_connection_pool(
        self,
        params: dict[str, Any],
    ) -> ConnectionPoolType_co: ...
    def get_connection_pool(self, params: dict[str, Any]) -> ConnectionPoolType_co: ...


class ConnectionFactory(
    ConnectionFactoryProtocol[RedisType, ConnectionPoolType, RedisParserType],
):
    # Store connection pool by cache backend options.
    #
    # _pools is a process-global, as otherwise _pools is cleared every time
    # ConnectionFactory is instantiated, as Django creates new cache client
    # (DefaultClient) instance for every request.

    _pools: dict[str, ConnectionPoolType] = {}

    def __init__(self, options: dict[str, Any]) -> None:
        pool_cls_path = options.get(
            "CONNECTION_POOL_CLASS",
            "redis.connection.ConnectionPool",
        )
        self.pool_cls: type[ConnectionPoolType] = import_string(pool_cls_path)
        self.pool_cls_kwargs: dict[str, Any] = options.get("CONNECTION_POOL_KWARGS", {})

        redis_client_cls_path = options.get("REDIS_CLIENT_CLASS", "redis.client.Redis")
        self.redis_client_cls: type[RedisType] = import_string(redis_client_cls_path)
        self.redis_client_cls_kwargs: dict[str, Any] = options.get(
            "REDIS_CLIENT_KWARGS",
            {},
        )

        self.options = options

    def make_connection_params(self, url: str) -> dict[str, Any]:
        """
        Given a main connection parameters, build a complete
        dict of connection parameters.
        """

        kwargs = {
            "url": url,
            "parser_class": self.get_parser_cls(),
        }

        username = self.options.get("USERNAME", None)
        if username:
            kwargs["username"] = username

        password = self.options.get("PASSWORD", None)
        if password:
            kwargs["password"] = password

        socket_timeout = self.options.get("SOCKET_TIMEOUT", None)
        if socket_timeout:
            if not isinstance(socket_timeout, (int, float)):
                error_message = "Socket timeout should be float or integer"
                raise ImproperlyConfigured(error_message)
            kwargs["socket_timeout"] = socket_timeout

        socket_connect_timeout = self.options.get("SOCKET_CONNECT_TIMEOUT", None)
        if socket_connect_timeout:
            if not isinstance(socket_connect_timeout, (int, float)):
                error_message = "Socket connect timeout should be float or integer"
                raise ImproperlyConfigured(error_message)
            kwargs["socket_connect_timeout"] = socket_connect_timeout

        return kwargs

    def connect(self, url: str) -> RedisType:
        """
        Given a basic connection parameters,
        return a new connection.
        """
        params = self.make_connection_params(url)
        return self.get_connection(params)

    def disconnect(self, connection: RedisType) -> None:
        """
        Given a not null client connection it disconnect from the Redis server.

        The default implementation uses a pool to hold connections.
        """
        connection.connection_pool.disconnect()

    def get_connection(self, params: dict[str, Any]) -> RedisType:
        """
        Given a now preformatted params, return a
        new connection.

        The default implementation uses a cached pools
        for create new connection.
        """
        pool = self.get_or_create_connection_pool(params)
        return self.redis_client_cls(
            connection_pool=pool,
            **self.redis_client_cls_kwargs,
        )

    def get_parser_cls(self) -> type[RedisParserType]:
        cls = self.options.get("PARSER_CLASS", None)
        if cls is None:
            return DefaultParser  # type: ignore[return-value]
        return cast("type[RedisParserType]", import_string(cls))

    def get_or_create_connection_pool(
        self,
        params: dict[str, Any],
    ) -> ConnectionPoolType:
        """
        Given a connection parameters and return a new
        or cached connection pool for them.

        Reimplement this method if you want distinct
        connection pool instance caching behavior.
        """
        key = params["url"]
        if key not in self._pools:
            self._pools[key] = self.get_connection_pool(params)
        return self._pools[key]

    def get_connection_pool(self, params: dict[str, Any]) -> ConnectionPoolType:
        """
        Given a connection parameters, return a new
        connection pool for them.

        Overwrite this method if you want a custom
        behavior on creating connection pool.
        """
        cp_params = dict(params)
        cp_params.update(self.pool_cls_kwargs)
        pool = self.pool_cls.from_url(**cp_params)

        if pool.connection_kwargs.get("password", None) is None:
            pool.connection_kwargs["password"] = params.get("password")
            pool.reset()

        return pool


class SentinelConnectionFactory(
    ConnectionFactory[RedisType, ConnectionPoolType, RedisParserType],
):
    def __init__(self, options: dict[str, Any]) -> None:
        # allow overriding the default SentinelConnectionPool class
        options.setdefault(
            "CONNECTION_POOL_CLASS",
            "redis.sentinel.SentinelConnectionPool",
        )
        super().__init__(options)

        sentinels = options.get("SENTINELS")
        if not sentinels:
            error_message = "SENTINELS must be provided as a list of (host, port)."
            raise ImproperlyConfigured(error_message)

        # provide the connection pool kwargs to the sentinel in case it
        # needs to use the socket options for the sentinels themselves
        connection_kwargs = self.make_connection_params("")
        connection_kwargs.pop("url")
        connection_kwargs.update(self.pool_cls_kwargs)
        self._sentinel = Sentinel(  # type: ignore[no-untyped-call]
            sentinels,
            sentinel_kwargs=options.get("SENTINEL_KWARGS"),
            **connection_kwargs,
        )

    def get_connection_pool(self, params: dict[str, Any]) -> ConnectionPoolType:
        """
        Given a connection parameters, return a new sentinel connection pool
        for them.
        """
        url = urlparse(params["url"])

        # explicitly set service_name and sentinel_manager for the
        # SentinelConnectionPool constructor since will be called by from_url
        cp_params = dict(params)
        # convert "is_master" to a boolean if set on the URL, otherwise if not
        # provided it defaults to True.
        query_params = parse_qs(url.query)
        is_master = query_params.get("is_master")
        if is_master:
            cp_params["is_master"] = to_bool(is_master[0])  # type: ignore[no-untyped-call]
        # then remove the "is_master" query string from the URL
        # so it doesn't interfere with the SentinelConnectionPool constructor
        if "is_master" in query_params:
            del query_params["is_master"]
        new_query = urlencode(query_params, doseq=True)

        new_url = urlunparse(
            (url.scheme, url.netloc, url.path, url.params, new_query, url.fragment),
        )

        cp_params.update(
            service_name=url.hostname,
            sentinel_manager=self._sentinel,
            url=new_url,
        )

        return super().get_connection_pool(cp_params)


def get_connection_factory(
    options: dict[str, Any],
) -> ConnectionFactoryProtocol[RedisType, ConnectionPoolType, RedisParserType]:
    cls: type[
        ConnectionFactoryProtocol[RedisType, ConnectionPoolType, RedisParserType]
    ] = import_string(
        options.get("CONNECTION_FACTORY")
        or cast(
            "str",
            getattr(
                settings,
                "DJANGO_REDIS_CONNECTION_FACTORY",
                "django_redis.pool.ConnectionFactory",
            ),
        ),
    )
    return cls(options)
