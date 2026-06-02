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


def test_make_connection_params_options():
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
