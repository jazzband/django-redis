import pytest
from django.core.exceptions import ImproperlyConfigured

from django_redis import pool


def test_connection_factory_redefine_from_opts():
    cf = pool.get_connection_factory(
        path="django_redis.pool.ConnectionFactory",
        options={
            "CONNECTION_FACTORY": "django_redis.pool.SentinelConnectionFactory",
            "SENTINELS": [("127.0.0.1", "26739")],
        },
    )
    assert cf.__class__.__name__ == "SentinelConnectionFactory"


@pytest.mark.parametrize(
    "conn_factory,expected",
    [
        ("django_redis.pool.SentinelConnectionFactory", pool.SentinelConnectionFactory),
        ("django_redis.pool.ConnectionFactory", pool.ConnectionFactory),
    ],
)
def test_connection_factory_opts(conn_factory: str, expected):
    cf = pool.get_connection_factory(
        path=None,
        options={
            "CONNECTION_FACTORY": conn_factory,
            "SENTINELS": [("127.0.0.1", "26739")],
        },
    )
    assert isinstance(cf, expected)


@pytest.mark.parametrize(
    "conn_factory,expected",
    [
        ("django_redis.pool.SentinelConnectionFactory", pool.SentinelConnectionFactory),
        ("django_redis.pool.ConnectionFactory", pool.ConnectionFactory),
    ],
)
def test_connection_factory_path(conn_factory: str, expected):
    cf = pool.get_connection_factory(
        path=conn_factory,
        options={
            "SENTINELS": [("127.0.0.1", "26739")],
        },
    )
    assert isinstance(cf, expected)


def test_connection_factory_no_sentinels():
    with pytest.raises(ImproperlyConfigured):
        pool.get_connection_factory(
            path=None,
            options={
                "CONNECTION_FACTORY": "django_redis.pool.SentinelConnectionFactory",
            },
        )
