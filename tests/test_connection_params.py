import pytest

from django_redis import pool


class TestConnectionParams:
    @pytest.mark.parametrize(
        "connection_string",
        [
            "unix://tmp/foo.bar?db=1",
            "redis://localhost/2",
            "rediss://localhost:3333?db=2",
        ],
    )
    def test_make_connection_params_url(self, connection_string: str):
        cf = pool.get_connection_factory(
            path="django_redis.pool.ConnectionFactory", options={}
        )
        res = cf.make_connection_params(connection_string)
        assert res["url"] == connection_string

    def test_make_connection_params_options(self):
        options = {
            "USERNAME": "django",
            "PASSWORD": "mysecret",
            "SOCKET_TIMEOUT": 5,
        }
        cf = pool.get_connection_factory(
            path="django_redis.pool.ConnectionFactory", options=options
        )
        res = cf.make_connection_params("")
        res.pop("url")
        res.pop("parser_class")
        assert res == {
            "username": "django",
            "password": "mysecret",
            "socket_timeout": 5,
        }
