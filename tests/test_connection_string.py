import pytest

from django_redis import pool


@pytest.mark.parametrize(
    "connection_string",
    [
        "unix://tmp/foo.bar?db=1",
        "redis://localhost/2",
        "rediss://localhost:3333?db=2",
    ],
)
def test_connection_strings(connection_string: str):
    cf = pool.get_connection_factory(
        path="django_redis.pool.ConnectionFactory", options={}
    )
    res = cf.make_connection_params(connection_string)
    assert res["url"] == connection_string
