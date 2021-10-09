import copy
import datetime
import threading
import time
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches
from django.test import override_settings
from redis.exceptions import ConnectionError

import django_redis.cache
from django_redis import pool
from django_redis.client import DefaultClient, ShardClient, herd
from django_redis.serializers.json import JSONSerializer
from django_redis.serializers.msgpack import MSGPackSerializer

herd.CACHE_HERD_TIMEOUT = 2


def make_key(key, prefix, version):
    return f"{prefix}#{version}#{key}"


def reverse_key(key):
    return key.split("#", 2)[2]


@pytest.mark.parametrize(
    "connection_string",
    [
        "unix://tmp/foo.bar?db=1",
        "redis://localhost/2",
        "rediss://localhost:3333?db=2",
    ],
)
def test_connection_strings(connection_string):
    cf = pool.get_connection_factory(
        path="django_redis.pool.ConnectionFactory", options={}
    )
    res = cf.make_connection_params(connection_string)
    assert res["url"] == connection_string


@pytest.fixture()
def key_prefix_cache(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["default"]["KEY_PREFIX"] = "*"
    settings.CACHES = caches_setting
    cache = caches["default"]
    yield cache
    cache.clear()


@pytest.fixture
def with_prefix_cache():
    with_prefix = caches["with_prefix"]
    yield with_prefix
    with_prefix.clear()


class TestDjangoRedisCacheEscapePrefix:
    def test_delete_pattern(self, key_prefix_cache, with_prefix_cache):
        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        key_prefix_cache.delete_pattern("*")
        assert key_prefix_cache.has_key("a") is False
        assert with_prefix_cache.get("b") == "2"

    def test_iter_keys(self, key_prefix_cache, with_prefix_cache):
        if isinstance(key_prefix_cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        assert list(key_prefix_cache.iter_keys("*")) == ["a"]

    def test_keys(self, key_prefix_cache, with_prefix_cache):
        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        keys = key_prefix_cache.keys("*")
        assert "a" in keys
        assert "b" not in keys


def test_custom_key_function(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["default"]["KEY_FUNCTION"] = "test_backend.make_key"
    caches_setting["default"]["REVERSE_KEY_FUNCTION"] = "test_backend.reverse_key"
    settings.CACHES = caches_setting
    cache = caches["default"]

    if isinstance(cache.client, ShardClient):
        pytest.skip("ShardClient doesn't support get_client")

    for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
        cache.set(key, "foo")

    res = cache.delete_pattern("*foo-a*")
    assert bool(res)

    keys = cache.keys("foo*")
    assert set(keys) == {"foo-bb", "foo-bc"}
    # ensure our custom function was actually called
    assert {k.decode() for k in cache.client.get_client(write=False).keys("*")} == (
        {"#1#foo-bc", "#1#foo-bb"}
    )
    cache.clear()


@pytest.fixture
def default_cache():
    yield cache
    cache.clear()


class TestDjangoRedisCache:
    def test_setnx(self, default_cache):
        # we should ensure there is no test_key_nx in redis
        default_cache.delete("test_key_nx")
        res = default_cache.get("test_key_nx")
        assert res is None

        res = default_cache.set("test_key_nx", 1, nx=True)
        assert res
        # test that second set will have
        res = default_cache.set("test_key_nx", 2, nx=True)
        assert not res
        res = default_cache.get("test_key_nx")
        assert res == 1

        default_cache.delete("test_key_nx")
        res = default_cache.get("test_key_nx")
        assert res is None

    def test_setnx_timeout(self, default_cache):
        # test that timeout still works for nx=True
        res = default_cache.set("test_key_nx", 1, timeout=2, nx=True)
        assert res
        time.sleep(3)
        res = default_cache.get("test_key_nx")
        assert res is None

        # test that timeout will not affect key, if it was there
        default_cache.set("test_key_nx", 1)
        res = default_cache.set("test_key_nx", 2, timeout=2, nx=True)
        assert not res
        time.sleep(3)
        res = default_cache.get("test_key_nx")
        assert res == 1

        default_cache.delete("test_key_nx")
        res = default_cache.get("test_key_nx")
        assert res is None

    def test_unicode_keys(self, default_cache):
        default_cache.set("ключ", "value")
        res = default_cache.get("ключ")
        assert res == "value"

    def test_save_and_integer(self, default_cache):
        default_cache.set("test_key", 2)
        res = default_cache.get("test_key", "Foo")

        assert isinstance(res, int)
        assert res == 2

    def test_save_string(self, default_cache):
        default_cache.set("test_key", "hello" * 1000)
        res = default_cache.get("test_key")

        assert isinstance(res, str)
        assert res == "hello" * 1000

        default_cache.set("test_key", "2")
        res = default_cache.get("test_key")

        assert isinstance(res, str)
        assert res == "2"

    def test_save_unicode(self, default_cache):
        default_cache.set("test_key", "heló")
        res = default_cache.get("test_key")

        assert isinstance(res, str)
        assert res == "heló"

    def test_save_dict(self, default_cache):
        if isinstance(
            default_cache.client._serializer, (JSONSerializer, MSGPackSerializer)
        ):
            # JSONSerializer and MSGPackSerializer use the isoformat for
            # datetimes.
            now_dt = datetime.datetime.now().isoformat()
        else:
            now_dt = datetime.datetime.now()

        test_dict = {"id": 1, "date": now_dt, "name": "Foo"}

        default_cache.set("test_key", test_dict)
        res = default_cache.get("test_key")

        assert isinstance(res, dict)
        assert res["id"] == 1
        assert res["name"] == "Foo"
        assert res["date"] == now_dt

    def test_save_float(self, default_cache):
        float_val = 1.345620002

        default_cache.set("test_key", float_val)
        res = default_cache.get("test_key")

        assert isinstance(res, float)
        assert res == float_val

    def test_timeout(self, default_cache):
        default_cache.set("test_key", 222, timeout=3)
        time.sleep(4)

        res = default_cache.get("test_key")
        assert res is None

    def test_timeout_0(self, default_cache):
        default_cache.set("test_key", 222, timeout=0)
        res = default_cache.get("test_key")
        assert res is None

    def test_timeout_parameter_as_positional_argument(self, default_cache):
        default_cache.set("test_key", 222, -1)
        res = default_cache.get("test_key")
        assert res is None

        default_cache.set("test_key", 222, 1)
        res1 = default_cache.get("test_key")
        time.sleep(2)
        res2 = default_cache.get("test_key")
        assert res1 == 222
        assert res2 is None

        # nx=True should not overwrite expire of key already in db
        default_cache.set("test_key", 222, None)
        default_cache.set("test_key", 222, -1, nx=True)
        res = default_cache.get("test_key")
        assert res == 222

    def test_timeout_negative(self, default_cache):
        default_cache.set("test_key", 222, timeout=-1)
        res = default_cache.get("test_key")
        assert res is None

        default_cache.set("test_key", 222, timeout=None)
        default_cache.set("test_key", 222, timeout=-1)
        res = default_cache.get("test_key")
        assert res is None

        # nx=True should not overwrite expire of key already in db
        default_cache.set("test_key", 222, timeout=None)
        default_cache.set("test_key", 222, timeout=-1, nx=True)
        res = default_cache.get("test_key")
        assert res == 222

    def test_timeout_tiny(self, default_cache):
        default_cache.set("test_key", 222, timeout=0.00001)
        res = default_cache.get("test_key")
        assert res in (None, 222)

    def test_set_add(self, default_cache):
        default_cache.set("add_key", "Initial value")
        res = default_cache.add("add_key", "New value")
        assert res is False

        res = cache.get("add_key")
        assert res == "Initial value"
        res = default_cache.add("other_key", "New value")
        assert res is True

    def test_get_many(self, default_cache):
        default_cache.set("a", 1)
        default_cache.set("b", 2)
        default_cache.set("c", 3)

        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"a": 1, "b": 2, "c": 3}

    def test_get_many_unicode(self, default_cache):
        default_cache.set("a", "1")
        default_cache.set("b", "2")
        default_cache.set("c", "3")

        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"a": "1", "b": "2", "c": "3"}

    def test_set_many(self, default_cache):
        default_cache.set_many({"a": 1, "b": 2, "c": 3})
        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"a": 1, "b": 2, "c": 3}

    def test_set_call_empty_pipeline(self, default_cache, mocker):
        if isinstance(default_cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        pipeline = default_cache.client.get_client(write=True).pipeline()
        key = "key"
        value = "value"

        mocked_set = mocker.patch.object(pipeline, "set")
        default_cache.set(key, value, client=pipeline)

        if isinstance(default_cache.client, herd.HerdClient):
            default_timeout = default_cache.client._backend.default_timeout
            herd_timeout = (default_timeout + herd.CACHE_HERD_TIMEOUT) * 1000
            herd_pack_value = default_cache.client._pack(value, default_timeout)
            mocked_set.assert_called_once_with(
                default_cache.client.make_key(key, version=None),
                default_cache.client.encode(herd_pack_value),
                nx=False,
                px=herd_timeout,
                xx=False,
            )
        else:
            mocked_set.assert_called_once_with(
                default_cache.client.make_key(key, version=None),
                default_cache.client.encode(value),
                nx=False,
                px=default_cache.client._backend.default_timeout * 1000,
                xx=False,
            )

    def test_delete(self, default_cache):
        default_cache.set_many({"a": 1, "b": 2, "c": 3})
        res = default_cache.delete("a")
        assert bool(res)

        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"b": 2, "c": 3}

        res = default_cache.delete("a")
        assert not bool(res)

    def test_delete_return_value_type_new31(self, default_cache, mocker):
        """delete() returns a boolean instead of int since django version 3.1"""
        mocker.patch("django_redis.cache.DJANGO_VERSION", new=(3, 1, 0, "final", 0))
        default_cache.set("a", 1)
        res = default_cache.delete("a")
        assert type(res) == bool
        assert res
        res = default_cache.delete("b")
        assert type(res) == bool
        assert not res

    def test_delete_return_value_type_before31(self, default_cache, mocker):
        """delete() returns a int before django version 3.1"""
        mocker.patch("django_redis.cache.DJANGO_VERSION", new=(3, 0, 1, "final", 0))
        default_cache.set("a", 1)
        res = default_cache.delete("a")
        assert type(res) == int
        assert res == 1
        res = default_cache.delete("b")
        assert type(res) == int
        assert res == 0

    def test_delete_many(self, default_cache):
        default_cache.set_many({"a": 1, "b": 2, "c": 3})
        res = default_cache.delete_many(["a", "b"])
        assert bool(res)

        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"c": 3}

        res = default_cache.delete_many(["a", "b"])
        assert not bool(res)

    def test_delete_many_generator(self, default_cache):
        default_cache.set_many({"a": 1, "b": 2, "c": 3})
        res = default_cache.delete_many(key for key in ["a", "b"])
        assert bool(res)

        res = default_cache.get_many(["a", "b", "c"])
        assert res == {"c": 3}

        res = default_cache.delete_many(["a", "b"])
        assert not bool(res)

    def test_delete_many_empty_generator(self, default_cache):
        res = default_cache.delete_many(key for key in [])
        assert not bool(res)

    def test_incr(self, default_cache):
        if isinstance(default_cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        default_cache.set("num", 1)

        default_cache.incr("num")
        res = default_cache.get("num")
        assert res == 2

        default_cache.incr("num", 10)
        res = default_cache.get("num")
        assert res == 12

        # max 64 bit signed int
        default_cache.set("num", 9223372036854775807)

        default_cache.incr("num")
        res = default_cache.get("num")
        assert res == 9223372036854775808

        default_cache.incr("num", 2)
        res = default_cache.get("num")
        assert res == 9223372036854775810

        default_cache.set("num", 3)

        default_cache.incr("num", 2)
        res = default_cache.get("num")
        assert res == 5

    def test_incr_no_timeout(self, default_cache):
        if isinstance(default_cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        default_cache.set("num", 1, timeout=None)

        default_cache.incr("num")
        res = default_cache.get("num")
        assert res == 2

        default_cache.incr("num", 10)
        res = default_cache.get("num")
        assert res == 12

        # max 64 bit signed int
        default_cache.set("num", 9223372036854775807, timeout=None)

        default_cache.incr("num")
        res = default_cache.get("num")
        assert res == 9223372036854775808

        default_cache.incr("num", 2)
        res = default_cache.get("num")
        assert res == 9223372036854775810

        default_cache.set("num", 3, timeout=None)

        default_cache.incr("num", 2)
        res = default_cache.get("num")
        assert res == 5

    def test_incr_error(self, default_cache):
        if isinstance(default_cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        with pytest.raises(ValueError):
            # key does not exist
            default_cache.incr("numnum")

    def test_incr_ignore_check(self, default_cache):
        if isinstance(default_cache.client, ShardClient):
            pytest.skip(
                "ShardClient doesn't support argument ignore_key_check to incr"
            )
        if isinstance(default_cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        # key exists check will be skipped and the value will be incremented by
        # '1' which is the default delta
        default_cache.incr("num", ignore_key_check=True)
        res = default_cache.get("num")
        assert res == 1
        default_cache.delete("num")

        # since key doesnt exist it is set to the delta value, 10 in this case
        default_cache.incr("num", 10, ignore_key_check=True)
        res = default_cache.get("num")
        assert res == 10
        default_cache.delete("num")

        # following are just regression checks to make sure it still works as
        # expected with incr max 64 bit signed int
        default_cache.set("num", 9223372036854775807)

        default_cache.incr("num", ignore_key_check=True)
        res = default_cache.get("num")
        assert res == 9223372036854775808

        default_cache.incr("num", 2, ignore_key_check=True)
        res = default_cache.get("num")
        assert res == 9223372036854775810

        default_cache.set("num", 3)

        default_cache.incr("num", 2, ignore_key_check=True)
        res = default_cache.get("num")
        assert res == 5

    def test_get_set_bool(self, default_cache):
        default_cache.set("bool", True)
        res = default_cache.get("bool")

        assert isinstance(res, bool)
        assert res is True

        default_cache.set("bool", False)
        res = default_cache.get("bool")

        assert isinstance(res, bool)
        assert res is False

    def test_decr(self, default_cache):
        if isinstance(default_cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support decr")

        default_cache.set("num", 20)

        default_cache.decr("num")
        res = default_cache.get("num")
        assert res == 19

        default_cache.decr("num", 20)
        res = default_cache.get("num")
        assert res == -1

        default_cache.decr("num", 2)
        res = default_cache.get("num")
        assert res == -3

        default_cache.set("num", 20)

        default_cache.decr("num")
        res = default_cache.get("num")
        assert res == 19

        # max 64 bit signed int + 1
        default_cache.set("num", 9223372036854775808)

        default_cache.decr("num")
        res = default_cache.get("num")
        assert res == 9223372036854775807

        default_cache.decr("num", 2)
        res = default_cache.get("num")
        assert res == 9223372036854775805

    def test_version(self, default_cache):
        default_cache.set("keytest", 2, version=2)
        res = default_cache.get("keytest")
        assert res is None

        res = default_cache.get("keytest", version=2)
        assert res == 2

    def test_incr_version(self, default_cache):
        default_cache.set("keytest", 2)
        default_cache.incr_version("keytest")

        res = default_cache.get("keytest")
        assert res is None

        res = default_cache.get("keytest", version=2)
        assert res == 2

    def test_ttl_incr_version_no_timeout(self, default_cache):
        default_cache.set("my_key", "hello world!", timeout=None)

        default_cache.incr_version("my_key")

        my_value = default_cache.get("my_key", version=2)

        assert my_value == "hello world!"

    def test_delete_pattern(self, default_cache):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            default_cache.set(key, "foo")

        res = default_cache.delete_pattern("*foo-a*")
        assert bool(res)

        keys = default_cache.keys("foo*")
        assert set(keys) == {"foo-bb", "foo-bc"}

        res = default_cache.delete_pattern("*foo-a*")
        assert not bool(res)

    def test_delete_pattern_with_custom_count(self, default_cache, mocker):
        client_mock = mocker.patch("django_redis.cache.RedisCache.client")
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            default_cache.set(key, "foo")

        default_cache.delete_pattern("*foo-a*", itersize=2)

        client_mock.delete_pattern.assert_called_once_with("*foo-a*", itersize=2)

    def test_delete_pattern_with_settings_default_scan_count(
        self, default_cache, mocker
    ):
        client_mock = mocker.patch("django_redis.cache.RedisCache.client")
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            default_cache.set(key, "foo")
        expected_count = django_redis.cache.DJANGO_REDIS_SCAN_ITERSIZE

        default_cache.delete_pattern("*foo-a*")

        client_mock.delete_pattern.assert_called_once_with(
            "*foo-a*", itersize=expected_count
        )

    def test_close(self, default_cache, settings):
        settings.DJANGO_REDIS_CLOSE_CONNECTION = True
        default_cache.set("f", "1")
        default_cache.close()

    def test_close_client(self, default_cache, mocker):
        mock = mocker.patch.object(default_cache.client, "close")
        default_cache.close()
        assert mock.called

    def test_ttl(self, default_cache):
        default_cache.set("foo", "bar", 10)
        ttl = default_cache.ttl("foo")

        if isinstance(default_cache.client, herd.HerdClient):
            assert pytest.approx(ttl) == 12
        else:
            assert pytest.approx(ttl) == 10

        # Test ttl None
        default_cache.set("foo", "foo", timeout=None)
        ttl = default_cache.ttl("foo")
        assert ttl is None

        # Test ttl with expired key
        default_cache.set("foo", "foo", timeout=-1)
        ttl = default_cache.ttl("foo")
        assert ttl == 0

        # Test ttl with not existent key
        ttl = default_cache.ttl("not-existent-key")
        assert ttl == 0

    def test_pttl(self, default_cache):

        # Test pttl
        default_cache.set("foo", "bar", 10)
        ttl = default_cache.pttl("foo")

        # delta is set to 10 as precision error causes tests to fail
        if isinstance(default_cache.client, herd.HerdClient):
            assert pytest.approx(ttl, 10) == 12000
        else:
            assert pytest.approx(ttl, 10) == 10000

        # Test pttl with float value
        default_cache.set("foo", "bar", 5.5)
        ttl = default_cache.pttl("foo")

        if isinstance(cache.client, herd.HerdClient):
            assert pytest.approx(ttl, 10) == 7500
        else:
            assert pytest.approx(ttl, 10) == 5500

        # Test pttl None
        default_cache.set("foo", "foo", timeout=None)
        ttl = default_cache.pttl("foo")
        assert ttl is None

        # Test pttl with expired key
        default_cache.set("foo", "foo", timeout=-1)
        ttl = default_cache.pttl("foo")
        assert ttl == 0

        # Test pttl with not existent key
        ttl = default_cache.pttl("not-existent-key")
        assert ttl == 0

    def test_persist(self, default_cache):
        default_cache.set("foo", "bar", timeout=20)
        default_cache.persist("foo")

        ttl = default_cache.ttl("foo")
        assert ttl is None

    def test_expire(self, default_cache):
        default_cache.set("foo", "bar", timeout=None)
        default_cache.expire("foo", 20)
        ttl = default_cache.ttl("foo")
        assert pytest.approx(ttl) == 20

    def test_pexpire(self, default_cache):
        default_cache.set("foo", "bar", timeout=None)
        default_cache.pexpire("foo", 20500)
        ttl = default_cache.pttl("foo")
        # delta is set to 10 as precision error causes tests to fail
        assert pytest.approx(ttl, 10) == 20500

    def test_expire_at(self, default_cache):

        # Test settings expiration time 1 hour ahead by datetime.
        default_cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=1)
        default_cache.expire_at("foo", expiration_time)
        ttl = default_cache.ttl("foo")
        assert pytest.approx(ttl, 1) == timedelta(hours=1).total_seconds()

        # Test settings expiration time 1 hour ahead by Unix timestamp.
        default_cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        default_cache.expire_at("foo", int(expiration_time.timestamp()))
        ttl = default_cache.ttl("foo")
        assert pytest.approx(ttl, 1) == timedelta(hours=1).total_seconds() * 2

        # Test settings expiration time 1 hour in past, which effectively
        # deletes the key.
        expiration_time = datetime.datetime.now() - timedelta(hours=2)
        default_cache.expire_at("foo", expiration_time)
        value = default_cache.get("foo")
        assert value is None

    def test_lock(self, default_cache):
        lock = default_cache.lock("foobar")
        lock.acquire(blocking=True)

        assert default_cache.has_key("foobar")
        lock.release()
        assert not default_cache.has_key("foobar")

    def test_lock_released_by_thread(self, default_cache):
        lock = default_cache.lock("foobar", thread_local=False)
        lock.acquire(blocking=True)

        def release_lock(lock_):
            lock_.release()

        t = threading.Thread(target=release_lock, args=[lock])
        t.start()
        t.join()

        assert not default_cache.has_key("foobar")

    def test_iter_keys(self, default_cache):
        cache = caches["default"]
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test simple result
        result = set(cache.iter_keys("foo*"))
        assert result == {"foo1", "foo2", "foo3"}

        # Test limited result
        result = list(cache.iter_keys("foo*", itersize=2))
        assert len(result) == 3

        # Test generator object
        result = cache.iter_keys("foo*")
        next_value = next(result)
        assert next_value is not None

    def test_primary_replica_switching(self, default_cache):
        if isinstance(default_cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        cache = caches["sample"]
        client = cache.client
        client._server = ["foo", "bar"]
        client._clients = ["Foo", "Bar"]

        assert client.get_client(write=True) == "Foo"
        assert client.get_client(write=False) == "Bar"

    def test_touch_zero_timeout(self, default_cache):
        default_cache.set("test_key", 222, timeout=10)

        assert default_cache.touch("test_key", 0) is True
        res = default_cache.get("test_key")
        assert res is None

    def test_touch_positive_timeout(self, default_cache):
        default_cache.set("test_key", 222, timeout=10)

        assert default_cache.touch("test_key", 2) is True
        assert default_cache.get("test_key") == 222
        time.sleep(3)
        assert default_cache.get("test_key") is None

    def test_touch_negative_timeout(self, default_cache):
        default_cache.set("test_key", 222, timeout=10)

        assert default_cache.touch("test_key", -1) is True
        res = default_cache.get("test_key")
        assert res is None

    def test_touch_missed_key(self, default_cache):
        assert default_cache.touch("test_key_does_not_exist", 1) is False

    def test_touch_forever(self, default_cache):
        default_cache.set("test_key", "foo", timeout=1)
        result = default_cache.touch("test_key", None)
        assert result is True
        assert default_cache.ttl("test_key") is None
        time.sleep(2)
        assert default_cache.get("test_key") == "foo"

    def test_touch_forever_nonexistent(self, default_cache):
        result = default_cache.touch("test_key_does_not_exist", None)
        assert result is False

    def test_touch_default_timeout(self, default_cache):
        default_cache.set("test_key", "foo", timeout=1)
        result = default_cache.touch("test_key")
        assert result is True
        time.sleep(2)
        assert default_cache.get("test_key") == "foo"

    def test_clear(self, default_cache):
        default_cache.set("foo", "bar")
        value_from_cache = default_cache.get("foo")
        assert value_from_cache == "bar"
        default_cache.clear()
        value_from_cache_after_clear = default_cache.get("foo")
        assert value_from_cache_after_clear is None


@pytest.fixture
def ignore_exceptions_cache(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
    cache = caches["doesnotexist"]
    yield caches["doesnotexist"]
    cache.clear()


def test_get_django_omit_exceptions_many_returns_default_arg(ignore_exceptions_cache):
    assert ignore_exceptions_cache._ignore_exceptions is True
    assert ignore_exceptions_cache.get_many(["key1", "key2", "key3"]) == {}


def test_get_django_omit_exceptions(ignore_exceptions_cache):
    assert ignore_exceptions_cache._ignore_exceptions is True
    assert ignore_exceptions_cache.get("key") is None
    assert ignore_exceptions_cache.get("key", "default") == "default"
    assert ignore_exceptions_cache.get("key", default="default") == "default"


def test_get_django_omit_exceptions_priority_1(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = False
    cache = caches["doesnotexist"]
    assert cache._ignore_exceptions is True
    assert cache.get("key") is None


def test_get_django_omit_exceptions_priority_2(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = False
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
    cache = caches["doesnotexist"]
    assert cache._ignore_exceptions is False
    with pytest.raises(ConnectionError):
        cache.get("key")


@pytest.fixture()
def default_cache_client():
    client = caches[DEFAULT_CACHE_ALIAS].client
    client.set("TestClientClose", 0)
    yield client
    client.delete("TestClientClose")
    client.clear()


class TestClientClose:
    def test_close_client_disconnect_default(self, default_cache_client, mocker):
        mock = mocker.patch.object(
            default_cache_client.connection_factory, "disconnect"
        )
        default_cache_client.close()
        assert not mock.called

    def test_close_disconnect_settings(self, default_cache_client, settings, mocker):
        settings.DJANGO_REDIS_CLOSE_CONNECTION = True
        mock = mocker.patch.object(
            default_cache_client.connection_factory, "disconnect"
        )
        default_cache_client.close()
        assert mock.called

    def test_close_disconnect_settings_cache(self, default_cache_client, mocker):
        settings.CACHES[DEFAULT_CACHE_ALIAS]["OPTIONS"]["CLOSE_CONNECTION"] = True
        with override_settings(CACHES=settings.CACHES):
            # enabling override_settings context emits 'setting_changed' signal
            # (re-set the value to populate again client connections)
            default_cache_client.set("TestClientClose", 0)
            mock = mocker.patch.object(
                default_cache_client.connection_factory, "disconnect"
            )
            default_cache_client.close()
            assert mock.called

    def test_close_disconnect_client_options(self, default_cache_client, mocker):
        default_cache_client._options["CLOSE_CONNECTION"] = True
        mock = mocker.patch.object(
            default_cache_client.connection_factory, "disconnect"
        )
        default_cache_client.close()
        assert mock.called


class TestDefaultClient:
    def test_delete_pattern_calls_get_client_given_no_client(self, mocker):
        get_client_mock = mocker.patch("test_backend.DefaultClient.get_client")
        mocker.patch("test_backend.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""

        client.delete_pattern(pattern="foo*")
        get_client_mock.assert_called_once_with(write=True)

    def test_delete_pattern_calls_make_pattern(self, mocker):
        make_pattern_mock = mocker.patch("test_backend.DefaultClient.make_pattern")
        get_client_mock = mocker.patch(
            "test_backend.DefaultClient.get_client", return_value=mocker.Mock()
        )
        mocker.patch("test_backend.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*")

        kwargs = {"version": None, "prefix": None}
        # if not isinstance(caches['default'].client, ShardClient):
        # kwargs['prefix'] = None

        make_pattern_mock.assert_called_once_with("foo*", **kwargs)

    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(self, mocker):
        make_pattern_mock = mocker.patch("test_backend.DefaultClient.make_pattern")
        get_client_mock = mocker.patch(
            "test_backend.DefaultClient.get_client", return_value=mocker.Mock()
        )
        mocker.patch("test_backend.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*", itersize=90210)

        get_client_mock.return_value.scan_iter.assert_called_once_with(
            count=90210, match=make_pattern_mock.return_value
        )


class TestShardClient:
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(self, mocker):
        mocker.patch("test_backend.ShardClient.__init__", return_value=None)
        make_pattern_mock = mocker.patch("test_backend.DefaultClient.make_pattern")
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""

        connection = mocker.Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*", itersize=10)

        connection.scan_iter.assert_called_once_with(
            count=10, match=make_pattern_mock.return_value
        )

    def test_delete_pattern_calls_scan_iter(self, mocker):
        make_pattern_mock = mocker.patch("test_backend.DefaultClient.make_pattern")
        mocker.patch("test_backend.ShardClient.__init__", return_value=None)
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        connection = mocker.Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.scan_iter.assert_called_once_with(
            match=make_pattern_mock.return_value
        )

    def test_delete_pattern_calls_delete_for_given_keys(self, mocker):
        mocker.patch("test_backend.DefaultClient.make_pattern")
        mocker.patch("test_backend.ShardClient.__init__", return_value=None)
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        connection = mocker.Mock()
        connection.scan_iter.return_value = [mocker.Mock(), mocker.Mock()]
        connection.delete.return_value = 0
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.delete.assert_called_once_with(*connection.scan_iter.return_value)
