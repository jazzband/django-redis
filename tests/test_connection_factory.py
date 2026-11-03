from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from django_redis import pool


def test_connection_factory_default():
    assert isinstance(pool.get_connection_factory({}), pool.ConnectionFactory)


def test_connection_factory_redefine_from_opts():
    assert isinstance(
        pool.get_connection_factory(
            {
                "CONNECTION_FACTORY": "django_redis.pool.SentinelConnectionFactory",
                "SENTINELS": [("127.0.0.1", "26739")],
            },
        ),
        pool.SentinelConnectionFactory,
    )


@pytest.mark.parametrize(
    "conn_factory,expected",
    [
        ("django_redis.pool.SentinelConnectionFactory", pool.SentinelConnectionFactory),
        ("django_redis.pool.ConnectionFactory", pool.ConnectionFactory),
    ],
)
def test_connection_factory_opts(conn_factory: str, expected):
    cf = pool.get_connection_factory(
        {
            "CONNECTION_FACTORY": conn_factory,
            "SENTINELS": [("127.0.0.1", "26739")],
        },
    )
    assert isinstance(cf, expected)


def test_sentinel_connection_factory_requires_sentinels():
    with pytest.raises(ImproperlyConfigured):
        pool.get_connection_factory(
            {
                "CONNECTION_FACTORY": "django_redis.pool.SentinelConnectionFactory",
            },
        )


def test_connection_pool_shared_for_identical_options():
    pool.ConnectionFactory._pools = {}
    factory = pool.ConnectionFactory({})
    url = "redis://localhost/0"
    first = factory.get_or_create_connection_pool(factory.make_connection_params(url))
    second = factory.get_or_create_connection_pool(factory.make_connection_params(url))
    assert first is second


def test_connection_pool_not_shared_for_different_socket_timeout():
    pool.ConnectionFactory._pools = {}
    url = "redis://localhost/0"
    short = pool.ConnectionFactory({"SOCKET_TIMEOUT": 1})
    long = pool.ConnectionFactory({"SOCKET_TIMEOUT": 5})
    short_pool = short.get_or_create_connection_pool(short.make_connection_params(url))
    long_pool = long.get_or_create_connection_pool(long.make_connection_params(url))
    assert short_pool is not long_pool
    assert short_pool.connection_kwargs.get("socket_timeout") == 1
    assert long_pool.connection_kwargs.get("socket_timeout") == 5


def test_sentinel_connection_pool_key_includes_sentinels():
    url = "redis://mymaster/0"
    first = pool.SentinelConnectionFactory({"SENTINELS": [("127.0.0.1", "26379")]})
    second = pool.SentinelConnectionFactory({"SENTINELS": [("127.0.0.1", "26380")]})
    first_key = first.get_connection_pool_key(first.make_connection_params(url))
    second_key = second.get_connection_pool_key(second.make_connection_params(url))
    assert first_key != second_key
