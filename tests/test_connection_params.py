from __future__ import annotations

import pytest

from django_redis import pool


@pytest.mark.parametrize(
    "connection_string",
    [
        "unix://tmp/foo.bar?db=1",
        "redis://localhost/2",
        "redis://redis-master/0?is_master=0",
        "redis://redis-master/2?is_master=False",
        "rediss://localhost:3333?db=2",
    ],
)
def test_connection_strings(connection_string: str):
    res = pool.ConnectionFactory({}).make_connection_params(connection_string)
    assert res["url"] == connection_string


def test_connection_options():
    params = pool.ConnectionFactory(
        {
            "USERNAME": "django",
            "PASSWORD": "mysecret",
            "SOCKET_TIMEOUT": 5,
        },
    ).make_connection_params("")
    assert (
        params.items()
        >= {
            "username": "django",
            "password": "mysecret",
            "socket_timeout": 5,
        }.items()
    )


@pytest.mark.parametrize(
    "config, expected",
    [
        # username and password tests
        (
            {
                "LOCATION": "redis://django:mysecret@localhost:6379/0",
            },
            {
                "username": "django",
                "password": "mysecret",
                "host": "localhost",
                "port": 6379,
            },
        ),
        (
            {
                "LOCATION": "redis://localhost:6379/0",
                "OPTIONS": {
                    "USERNAME": "django",
                    "PASSWORD": "mysecret",
                },
            },
            {
                "username": "django",
                "password": "mysecret",
            },
        ),
        (
            {
                "LOCATION": "redis://django@localhost:6379/0",
                "OPTIONS": {"PASSWORD": "mysecret"},
            },
            {
                "username": "django",
                "password": "mysecret",
            },
        ),
        # url has precedence!
        (
            {
                "LOCATION": "redis://django:old-password@localhost:6379/0",
                "OPTIONS": {"PASSWORD": "mysecret"},
            },
            {
                "username": "django",
                "password": "old-password",
            },
        ),
    ],
)
def test_connection_connection_kwargs(config, expected):
    factory = pool.ConnectionFactory(config.get("OPTIONS", {}))
    assert (
        factory.get_connection_pool(
            factory.make_connection_params(config["LOCATION"]),
        ).connection_kwargs.items()
        >= expected.items()
    )
