import datetime
import threading
import time
from datetime import timedelta
from typing import List, Union, cast
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import caches
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

import django_redis.cache
from django_redis.cache import RedisCache
from django_redis.client import ShardClient, herd
from django_redis.serializers.json import JSONSerializer
from django_redis.serializers.msgpack import MSGPackSerializer


class TestDjangoRedisCache:
    def test_setnx(self, cache: RedisCache):
        # we should ensure there is no test_key_nx in redis
        cache.delete("test_key_nx")
        res = cache.get("test_key_nx")
        assert res is None

        res = cache.set("test_key_nx", 1, nx=True)
        assert bool(res) is True
        # test that second set will have
        res = cache.set("test_key_nx", 2, nx=True)
        assert res is False
        res = cache.get("test_key_nx")
        assert res == 1

        cache.delete("test_key_nx")
        res = cache.get("test_key_nx")
        assert res is None

    def test_setnx_timeout(self, cache: RedisCache):
        # test that timeout still works for nx=True
        res = cache.set("test_key_nx", 1, timeout=2, nx=True)
        assert res is True
        time.sleep(3)
        res = cache.get("test_key_nx")
        assert res is None

        # test that timeout will not affect key, if it was there
        cache.set("test_key_nx", 1)
        res = cache.set("test_key_nx", 2, timeout=2, nx=True)
        assert res is False
        time.sleep(3)
        res = cache.get("test_key_nx")
        assert res == 1

        cache.delete("test_key_nx")
        res = cache.get("test_key_nx")
        assert res is None

    def test_unicode_keys(self, cache: RedisCache):
        cache.set("ключ", "value")
        res = cache.get("ключ")
        assert res == "value"

    def test_save_and_integer(self, cache: RedisCache):
        cache.set("test_key", 2)
        res = cache.get("test_key", "Foo")

        assert isinstance(res, int)
        assert res == 2

    def test_save_string(self, cache: RedisCache):
        cache.set("test_key", "hello" * 1000)
        res = cache.get("test_key")

        assert isinstance(res, str)
        assert res == "hello" * 1000

        cache.set("test_key", "2")
        res = cache.get("test_key")

        assert isinstance(res, str)
        assert res == "2"

    def test_save_unicode(self, cache: RedisCache):
        cache.set("test_key", "heló")
        res = cache.get("test_key")

        assert isinstance(res, str)
        assert res == "heló"

    def test_save_dict(self, cache: RedisCache):
        if isinstance(cache.client._serializer, (JSONSerializer, MSGPackSerializer)):
            # JSONSerializer and MSGPackSerializer use the isoformat for
            # datetimes.
            now_dt: Union[str, datetime.datetime] = datetime.datetime.now().isoformat()
        else:
            now_dt = datetime.datetime.now()

        test_dict = {"id": 1, "date": now_dt, "name": "Foo"}

        cache.set("test_key", test_dict)
        res = cache.get("test_key")

        assert isinstance(res, dict)
        assert res["id"] == 1
        assert res["name"] == "Foo"
        assert res["date"] == now_dt

    def test_save_float(self, cache: RedisCache):
        float_val = 1.345620002

        cache.set("test_key", float_val)
        res = cache.get("test_key")

        assert isinstance(res, float)
        assert res == float_val

    def test_timeout(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=3)
        time.sleep(4)

        res = cache.get("test_key")
        assert res is None

    def test_timeout_0(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=0)
        res = cache.get("test_key")
        assert res is None

    def test_timeout_parameter_as_positional_argument(self, cache: RedisCache):
        cache.set("test_key", 222, -1)
        res = cache.get("test_key")
        assert res is None

        cache.set("test_key", 222, 1)
        res1 = cache.get("test_key")
        time.sleep(2)
        res2 = cache.get("test_key")
        assert res1 == 222
        assert res2 is None

        # nx=True should not overwrite expire of key already in db
        cache.set("test_key", 222, None)
        cache.set("test_key", 222, -1, nx=True)
        res = cache.get("test_key")
        assert res == 222

    def test_timeout_negative(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=-1)
        res = cache.get("test_key")
        assert res is None

        cache.set("test_key", 222, timeout=None)
        cache.set("test_key", 222, timeout=-1)
        res = cache.get("test_key")
        assert res is None

        # nx=True should not overwrite expire of key already in db
        cache.set("test_key", 222, timeout=None)
        cache.set("test_key", 222, timeout=-1, nx=True)
        res = cache.get("test_key")
        assert res == 222

    def test_timeout_tiny(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=0.00001)
        res = cache.get("test_key")
        assert res in (None, 222)

    def test_set_add(self, cache: RedisCache):
        cache.set("add_key", "Initial value")
        res = cache.add("add_key", "New value")
        assert res is False

        res = cache.get("add_key")
        assert res == "Initial value"
        res = cache.add("other_key", "New value")
        assert res is True

    def test_get_many(self, cache: RedisCache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        res = cache.get_many(["a", "b", "c"])
        assert res == {"a": 1, "b": 2, "c": 3}

    def test_get_many_unicode(self, cache: RedisCache):
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")

        res = cache.get_many(["a", "b", "c"])
        assert res == {"a": "1", "b": "2", "c": "3"}

    def test_set_many(self, cache: RedisCache):
        cache.set_many({"a": 1, "b": 2, "c": 3})
        res = cache.get_many(["a", "b", "c"])
        assert res == {"a": 1, "b": 2, "c": 3}

    def test_set_call_empty_pipeline(self, cache: RedisCache, mocker: MockerFixture, settings: SettingsWrapper):
        settings.CACHE_HERD_TIMEOUT = 2

        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        pipeline = cache.client.get_client(write=True).pipeline()
        key = "key"
        value = "value"

        mocked_set = mocker.patch.object(pipeline, "set")
        cache.set(key, value, client=pipeline)

        if isinstance(cache.client, herd.HerdClient):
            default_timeout = cache.client._backend.default_timeout
            herd_timeout = (default_timeout + settings.CACHE_HERD_TIMEOUT) * 1000  # type: ignore # noqa
            herd_pack_value = cache.client._pack(value, default_timeout)
            mocked_set.assert_called_once_with(
                cache.client.make_key(key, version=None),
                cache.client.encode(herd_pack_value),
                nx=False,
                px=herd_timeout,
                xx=False,
            )
        else:
            mocked_set.assert_called_once_with(
                cache.client.make_key(key, version=None),
                cache.client.encode(value),
                nx=False,
                px=cache.client._backend.default_timeout * 1000,
                xx=False,
            )

    def test_delete(self, cache: RedisCache):
        cache.set_many({"a": 1, "b": 2, "c": 3})
        res = cache.delete("a")
        assert bool(res) is True

        res = cache.get_many(["a", "b", "c"])
        assert res == {"b": 2, "c": 3}

        res = cache.delete("a")
        assert bool(res) is False

    @patch("django_redis.cache.DJANGO_VERSION", (3, 1, 0, "final", 0))
    def test_delete_return_value_type_new31(self, cache: RedisCache):
        """delete() returns a boolean instead of int since django version 3.1"""
        cache.set("a", 1)
        res = cache.delete("a")
        assert isinstance(res, bool)
        assert res is True
        res = cache.delete("b")
        assert isinstance(res, bool)
        assert res is False

    @patch("django_redis.cache.DJANGO_VERSION", new=(3, 0, 1, "final", 0))
    def test_delete_return_value_type_before31(self, cache: RedisCache):
        """delete() returns a int before django version 3.1"""
        cache.set("a", 1)
        res = cache.delete("a")
        assert isinstance(res, int)
        assert res == 1
        res = cache.delete("b")
        assert isinstance(res, int)
        assert res == 0

    def test_delete_many(self, cache: RedisCache):
        cache.set_many({"a": 1, "b": 2, "c": 3})
        res = cache.delete_many(["a", "b"])
        assert bool(res) is True

        res = cache.get_many(["a", "b", "c"])
        assert res == {"c": 3}

        res = cache.delete_many(["a", "b"])
        assert bool(res) is False

    def test_delete_many_generator(self, cache: RedisCache):
        cache.set_many({"a": 1, "b": 2, "c": 3})
        res = cache.delete_many(key for key in ["a", "b"])
        assert bool(res) is True

        res = cache.get_many(["a", "b", "c"])
        assert res == {"c": 3}

        res = cache.delete_many(["a", "b"])
        assert bool(res) is False

    def test_delete_many_empty_generator(self, cache: RedisCache):
        res = cache.delete_many(key for key in cast(List[str], []))
        assert bool(res) is False

    def test_incr(self, cache: RedisCache):
        if isinstance(cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        cache.set("num", 1)

        cache.incr("num")
        res = cache.get("num")
        assert res == 2

        cache.incr("num", 10)
        res = cache.get("num")
        assert res == 12

        # max 64 bit signed int
        cache.set("num", 9223372036854775807)

        cache.incr("num")
        res = cache.get("num")
        assert res == 9223372036854775808

        cache.incr("num", 2)
        res = cache.get("num")
        assert res == 9223372036854775810

        cache.set("num", 3)

        cache.incr("num", 2)
        res = cache.get("num")
        assert res == 5

    def test_incr_no_timeout(self, cache: RedisCache):
        if isinstance(cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        cache.set("num", 1, timeout=None)

        cache.incr("num")
        res = cache.get("num")
        assert res == 2

        cache.incr("num", 10)
        res = cache.get("num")
        assert res == 12

        # max 64 bit signed int
        cache.set("num", 9223372036854775807, timeout=None)

        cache.incr("num")
        res = cache.get("num")
        assert res == 9223372036854775808

        cache.incr("num", 2)
        res = cache.get("num")
        assert res == 9223372036854775810

        cache.set("num", 3, timeout=None)

        cache.incr("num", 2)
        res = cache.get("num")
        assert res == 5

    def test_incr_error(self, cache: RedisCache):
        if isinstance(cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        with pytest.raises(ValueError):
            # key does not exist
            cache.incr("numnum")

    def test_incr_ignore_check(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support argument ignore_key_check to incr")
        if isinstance(cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support incr")

        # key exists check will be skipped and the value will be incremented by
        # '1' which is the default delta
        cache.incr("num", ignore_key_check=True)
        res = cache.get("num")
        assert res == 1
        cache.delete("num")

        # since key doesnt exist it is set to the delta value, 10 in this case
        cache.incr("num", 10, ignore_key_check=True)
        res = cache.get("num")
        assert res == 10
        cache.delete("num")

        # following are just regression checks to make sure it still works as
        # expected with incr max 64 bit signed int
        cache.set("num", 9223372036854775807)

        cache.incr("num", ignore_key_check=True)
        res = cache.get("num")
        assert res == 9223372036854775808

        cache.incr("num", 2, ignore_key_check=True)
        res = cache.get("num")
        assert res == 9223372036854775810

        cache.set("num", 3)

        cache.incr("num", 2, ignore_key_check=True)
        res = cache.get("num")
        assert res == 5

    def test_get_set_bool(self, cache: RedisCache):
        cache.set("bool", True)
        res = cache.get("bool")

        assert isinstance(res, bool)
        assert res is True

        cache.set("bool", False)
        res = cache.get("bool")

        assert isinstance(res, bool)
        assert res is False

    def test_decr(self, cache: RedisCache):
        if isinstance(cache.client, herd.HerdClient):
            pytest.skip("HerdClient doesn't support decr")

        cache.set("num", 20)

        cache.decr("num")
        res = cache.get("num")
        assert res == 19

        cache.decr("num", 20)
        res = cache.get("num")
        assert res == -1

        cache.decr("num", 2)
        res = cache.get("num")
        assert res == -3

        cache.set("num", 20)

        cache.decr("num")
        res = cache.get("num")
        assert res == 19

        # max 64 bit signed int + 1
        cache.set("num", 9223372036854775808)

        cache.decr("num")
        res = cache.get("num")
        assert res == 9223372036854775807

        cache.decr("num", 2)
        res = cache.get("num")
        assert res == 9223372036854775805

    def test_version(self, cache: RedisCache):
        cache.set("keytest", 2, version=2)
        res = cache.get("keytest")
        assert res is None

        res = cache.get("keytest", version=2)
        assert res == 2

    def test_incr_version(self, cache: RedisCache):
        cache.set("keytest", 2)
        cache.incr_version("keytest")

        res = cache.get("keytest")
        assert res is None

        res = cache.get("keytest", version=2)
        assert res == 2

    def test_ttl_incr_version_no_timeout(self, cache: RedisCache):
        cache.set("my_key", "hello world!", timeout=None)

        cache.incr_version("my_key")

        my_value = cache.get("my_key", version=2)

        assert my_value == "hello world!"

    def test_delete_pattern(self, cache: RedisCache):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            cache.set(key, "foo")

        res = cache.delete_pattern("*foo-a*")
        assert bool(res) is True

        keys = cache.keys("foo*")
        assert set(keys) == {"foo-bb", "foo-bc"}

        res = cache.delete_pattern("*foo-a*")
        assert bool(res) is False

    @patch("django_redis.cache.RedisCache.client")
    def test_delete_pattern_with_custom_count(self, client_mock, cache: RedisCache):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            cache.set(key, "foo")

        cache.delete_pattern("*foo-a*", itersize=2)

        client_mock.delete_pattern.assert_called_once_with("*foo-a*", itersize=2)

    @patch("django_redis.cache.RedisCache.client")
    def test_delete_pattern_with_settings_default_scan_count(
        self, client_mock, cache: RedisCache, settings: SettingsWrapper,
    ):
        settings.DJANGO_REDIS_SCAN_ITERSIZE = 30

        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            cache.set(key, "foo")
        expected_count = settings.DJANGO_REDIS_SCAN_ITERSIZE

        cache.delete_pattern("*foo-a*")

        client_mock.delete_pattern.assert_called_once_with(
            "*foo-a*", itersize=expected_count
        )

    def test_close(self, cache: RedisCache, settings: SettingsWrapper):
        settings.DJANGO_REDIS_CLOSE_CONNECTION = True
        cache.set("f", "1")
        cache.close()

    def test_close_client(self, cache: RedisCache, mocker: MockerFixture):
        mock = mocker.patch.object(cache.client, "close")
        cache.close()
        assert mock.called

    def test_ttl(self, cache: RedisCache):
        cache.set("foo", "bar", 10)
        ttl = cache.ttl("foo")

        if isinstance(cache.client, herd.HerdClient):
            assert pytest.approx(ttl) == 12
        else:
            assert pytest.approx(ttl) == 10

        # Test ttl None
        cache.set("foo", "foo", timeout=None)
        ttl = cache.ttl("foo")
        assert ttl is None

        # Test ttl with expired key
        cache.set("foo", "foo", timeout=-1)
        ttl = cache.ttl("foo")
        assert ttl == 0

        # Test ttl with not existent key
        ttl = cache.ttl("not-existent-key")
        assert ttl == 0

    def test_pttl(self, cache: RedisCache):
        # Test pttl
        cache.set("foo", "bar", 10)
        ttl = cache.pttl("foo")

        # delta is set to 10 as precision error causes tests to fail
        if isinstance(cache.client, herd.HerdClient):
            assert pytest.approx(ttl, 10) == 12000
        else:
            assert pytest.approx(ttl, 10) == 10000

        # Test pttl with float value
        cache.set("foo", "bar", 5.5)
        ttl = cache.pttl("foo")

        if isinstance(cache.client, herd.HerdClient):
            assert pytest.approx(ttl, 10) == 7500
        else:
            assert pytest.approx(ttl, 10) == 5500

        # Test pttl None
        cache.set("foo", "foo", timeout=None)
        ttl = cache.pttl("foo")
        assert ttl is None

        # Test pttl with expired key
        cache.set("foo", "foo", timeout=-1)
        ttl = cache.pttl("foo")
        assert ttl == 0

        # Test pttl with not existent key
        ttl = cache.pttl("not-existent-key")
        assert ttl == 0

    def test_persist(self, cache: RedisCache):
        cache.set("foo", "bar", timeout=20)
        assert cache.persist("foo") is True

        ttl = cache.ttl("foo")
        assert ttl is None
        assert cache.persist("not-existent-key") is False

    def test_expire(self, cache: RedisCache):
        cache.set("foo", "bar", timeout=None)
        assert cache.expire("foo", 20) is True
        ttl = cache.ttl("foo")
        assert pytest.approx(ttl) == 20
        assert cache.expire("not-existent-key", 20) is False

    def test_pexpire(self, cache: RedisCache):
        cache.set("foo", "bar", timeout=None)
        assert cache.pexpire("foo", 20500) is True
        ttl = cache.pttl("foo")
        # delta is set to 10 as precision error causes tests to fail
        assert pytest.approx(ttl, 10) == 20500
        assert cache.pexpire("not-existent-key", 20500) is False

    def test_pexpire_at(self, cache: RedisCache):
        # Test settings expiration time 1 hour ahead by datetime.
        cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=1)
        assert cache.pexpire_at("foo", expiration_time) is True
        ttl = cache.pttl("foo")
        assert pytest.approx(ttl, 10) == timedelta(hours=1).total_seconds()

        # Test settings expiration time 1 hour ahead by Unix timestamp.
        cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        assert cache.pexpire_at("foo", int(expiration_time.timestamp() * 1000)) is True
        ttl = cache.pttl("foo")
        assert pytest.approx(ttl, 10) == timedelta(hours=2).total_seconds() * 1000

        # Test settings expiration time 1 hour in past, which effectively
        # deletes the key.
        expiration_time = datetime.datetime.now() - timedelta(hours=2)
        assert cache.pexpire_at("foo", expiration_time) is True
        value = cache.get("foo")
        assert value is None

        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        assert cache.pexpire_at("not-existent-key", expiration_time) is False

    def test_expire_at(self, cache: RedisCache):
        # Test settings expiration time 1 hour ahead by datetime.
        cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=1)
        assert cache.expire_at("foo", expiration_time) is True
        ttl = cache.ttl("foo")
        assert pytest.approx(ttl, 1) == timedelta(hours=1).total_seconds()

        # Test settings expiration time 1 hour ahead by Unix timestamp.
        cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        assert cache.expire_at("foo", int(expiration_time.timestamp())) is True
        ttl = cache.ttl("foo")
        assert pytest.approx(ttl, 1) == timedelta(hours=1).total_seconds() * 2

        # Test settings expiration time 1 hour in past, which effectively
        # deletes the key.
        expiration_time = datetime.datetime.now() - timedelta(hours=2)
        assert cache.expire_at("foo", expiration_time) is True
        value = cache.get("foo")
        assert value is None

        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        assert cache.expire_at("not-existent-key", expiration_time) is False

    def test_lock(self, cache: RedisCache):
        lock = cache.lock("foobar")
        lock.acquire(blocking=True)

        assert cache.has_key("foobar")
        lock.release()
        assert not cache.has_key("foobar")

    def test_lock_released_by_thread(self, cache: RedisCache):
        lock = cache.lock("foobar", thread_local=False)
        lock.acquire(blocking=True)

        def release_lock(lock_):
            lock_.release()

        t = threading.Thread(target=release_lock, args=[lock])
        t.start()
        t.join()

        assert not cache.has_key("foobar")

    def test_iter_keys(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test simple result
        result = set(cache.iter_keys("foo*"))
        assert result == {"foo1", "foo2", "foo3"}

    def test_iter_keys_itersize(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test limited result
        result = list(cache.iter_keys("foo*", itersize=2))
        assert len(result) == 3

    def test_iter_keys_generator(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test generator object
        result = cache.iter_keys("foo*")
        next_value = next(result)
        assert next_value is not None

    def test_primary_replica_switching(self, cache: RedisCache):
        if isinstance(cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support get_client")

        cache = cast(RedisCache, caches["sample"])
        client = cache.client
        client._server = ["foo", "bar"]
        client._clients = ["Foo", "Bar"]

        assert client.get_client(write=True) == "Foo"
        assert client.get_client(write=False) == "Bar"

    def test_touch_zero_timeout(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=10)

        assert cache.touch("test_key", 0) is True
        res = cache.get("test_key")
        assert res is None

    def test_touch_positive_timeout(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=10)

        assert cache.touch("test_key", 2) is True
        assert cache.get("test_key") == 222
        time.sleep(3)
        assert cache.get("test_key") is None

    def test_touch_negative_timeout(self, cache: RedisCache):
        cache.set("test_key", 222, timeout=10)

        assert cache.touch("test_key", -1) is True
        res = cache.get("test_key")
        assert res is None

    def test_touch_missed_key(self, cache: RedisCache):
        assert cache.touch("test_key_does_not_exist", 1) is False

    def test_touch_forever(self, cache: RedisCache):
        cache.set("test_key", "foo", timeout=1)
        result = cache.touch("test_key", None)
        assert result is True
        assert cache.ttl("test_key") is None
        time.sleep(2)
        assert cache.get("test_key") == "foo"

    def test_touch_forever_nonexistent(self, cache: RedisCache):
        result = cache.touch("test_key_does_not_exist", None)
        assert result is False

    def test_touch_default_timeout(self, cache: RedisCache):
        cache.set("test_key", "foo", timeout=1)
        result = cache.touch("test_key")
        assert result is True
        time.sleep(2)
        assert cache.get("test_key") == "foo"

    def test_clear(self, cache: RedisCache):
        cache.set("foo", "bar")
        value_from_cache = cache.get("foo")
        assert value_from_cache == "bar"
        cache.clear()
        value_from_cache_after_clear = cache.get("foo")
        assert value_from_cache_after_clear is None
