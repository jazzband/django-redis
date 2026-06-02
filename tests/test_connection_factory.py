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
