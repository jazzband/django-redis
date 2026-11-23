from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from redis.credentials import CredentialProvider

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


@pytest.mark.parametrize(
    "factory_class",
    [pool.ConnectionFactory, pool.SentinelConnectionFactory],
)
def test_credential_provider_from_dotted_path(factory_class):
    pool_kwargs = {"credential_provider": "redis.credentials.CredentialProvider"}
    factory = factory_class(
        {
            "CONNECTION_POOL_KWARGS": pool_kwargs,
            "SENTINELS": [("127.0.0.1", 26379)],
        },
    )
    connection_pool = factory.get_connection_pool(
        factory.make_connection_params("redis://localhost/0"),
    )
    provider = connection_pool.connection_kwargs["credential_provider"]

    assert isinstance(provider, CredentialProvider)
    assert pool_kwargs["credential_provider"] == "redis.credentials.CredentialProvider"
    if isinstance(factory, pool.SentinelConnectionFactory):
        assert factory._sentinel.connection_kwargs["credential_provider"] is provider


@pytest.mark.parametrize(
    "provider",
    [None, pytest.param(CredentialProvider(), id="instance")],
)
def test_credential_provider_preserves_existing_values(provider):
    factory = pool.ConnectionFactory(
        {"CONNECTION_POOL_KWARGS": {"credential_provider": provider}},
    )
    connection_pool = factory.get_connection_pool(
        factory.make_connection_params("redis://localhost/0"),
    )

    assert connection_pool.connection_kwargs["credential_provider"] is provider


def test_credential_provider_invalid_dotted_path():
    with pytest.raises(ImportError, match="does not define"):
        pool.ConnectionFactory(
            {
                "CONNECTION_POOL_KWARGS": {
                    "credential_provider": "redis.credentials.MissingProvider",
                },
            },
        )
