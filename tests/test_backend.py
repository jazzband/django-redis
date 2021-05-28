import base64
import copy
import datetime
import threading
import time
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore as CacheSession
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches
from django.test import override_settings
from django.utils import timezone
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


class DjangoRedisConnectionStrings(unittest.TestCase):
    def test_connection_strings(self):
        connection_strings = [
            "unix://tmp/foo.bar?db=1",
            "redis://localhost/2",
            "rediss://localhost:3333?db=2",
        ]
        cf = pool.get_connection_factory(
            path="django_redis.pool.ConnectionFactory", options={}
        )
        for connection_string in connection_strings:
            with self.subTest(connection_string):
                res = cf.make_connection_params(connection_string)
                self.assertEqual(res["url"], connection_string)


class DjangoRedisCacheTestEscapePrefix(unittest.TestCase):
    def setUp(self):

        caches_setting = copy.deepcopy(settings.CACHES)
        caches_setting["default"]["KEY_PREFIX"] = "*"
        cm = override_settings(CACHES=caches_setting)
        cm.enable()
        self.addCleanup(cm.disable)

        self.cache = caches["default"]
        self.other = caches["with_prefix"]

    def tearDown(self):
        self.cache.clear()
        self.other.clear()

    def test_delete_pattern(self):
        self.cache.set("a", "1")
        self.other.set("b", "2")
        self.cache.delete_pattern("*")
        self.assertIs(self.cache.has_key("a"), False)
        self.assertEqual(self.other.get("b"), "2")

    def test_iter_keys(self):
        if isinstance(self.cache.client, ShardClient):
            self.skipTest("ShardClient doesn't support iter_keys")

        self.cache.set("a", "1")
        self.other.set("b", "2")
        self.assertEqual(list(self.cache.iter_keys("*")), ["a"])

    def test_keys(self):
        self.cache.set("a", "1")
        self.other.set("b", "2")
        keys = self.cache.keys("*")
        self.assertIn("a", keys)
        self.assertNotIn("b", keys)


class DjangoRedisCacheTestCustomKeyFunction(unittest.TestCase):
    def setUp(self):
        caches_setting = copy.deepcopy(settings.CACHES)
        caches_setting["default"]["KEY_FUNCTION"] = "test_backend.make_key"
        caches_setting["default"]["REVERSE_KEY_FUNCTION"] = "test_backend.reverse_key"
        cm = override_settings(CACHES=caches_setting)
        cm.enable()
        self.addCleanup(cm.disable)

        self.cache = caches["default"]

    def tearDown(self):
        self.cache.clear()

    def test_custom_key_function(self):
        if isinstance(self.cache.client, ShardClient):
            self.skipTest("ShardClient doesn't support get_client")

        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), {"foo-bb", "foo-bc"})
        # ensure our custom function was actually called
        self.assertEqual(
            {k.decode() for k in self.cache.client.get_client(write=False).keys("*")},
            {"#1#foo-bc", "#1#foo-bb"},
        )


class DjangoRedisCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = cache

    def tearDown(self):
        self.cache.clear()

    def test_setnx(self):
        # we should ensure there is no test_key_nx in redis
        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx")
        self.assertIsNone(res)

        res = self.cache.set("test_key_nx", 1, nx=True)
        self.assertTrue(res)
        # test that second set will have
        res = self.cache.set("test_key_nx", 2, nx=True)
        self.assertFalse(res)
        res = self.cache.get("test_key_nx")
        self.assertEqual(res, 1)

        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx")
        self.assertIsNone(res)

    def test_setnx_timeout(self):
        # test that timeout still works for nx=True
        res = self.cache.set("test_key_nx", 1, timeout=2, nx=True)
        self.assertTrue(res)
        time.sleep(3)
        res = self.cache.get("test_key_nx")
        self.assertIsNone(res)

        # test that timeout will not affect key, if it was there
        self.cache.set("test_key_nx", 1)
        res = self.cache.set("test_key_nx", 2, timeout=2, nx=True)
        self.assertFalse(res)
        time.sleep(3)
        res = self.cache.get("test_key_nx")
        self.assertEqual(res, 1)

        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx")
        self.assertIsNone(res)

    def test_unicode_keys(self):
        self.cache.set("ключ", "value")
        res = self.cache.get("ключ")
        self.assertEqual(res, "value")

    def test_save_and_integer(self):
        self.cache.set("test_key", 2)
        res = self.cache.get("test_key", "Foo")

        self.assertIsInstance(res, int)
        self.assertEqual(res, 2)

    def test_save_string(self):
        self.cache.set("test_key", "hello" * 1000)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, str)
        self.assertEqual(res, "hello" * 1000)

        self.cache.set("test_key", "2")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, str)
        self.assertEqual(res, "2")

    def test_save_unicode(self):
        self.cache.set("test_key", "heló")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, str)
        self.assertEqual(res, "heló")

    def test_save_dict(self):
        if isinstance(
            self.cache.client._serializer, (JSONSerializer, MSGPackSerializer)
        ):
            # JSONSerializer and MSGPackSerializer use the isoformat for
            # datetimes.
            now_dt = datetime.datetime.now().isoformat()
        else:
            now_dt = datetime.datetime.now()

        test_dict = {"id": 1, "date": now_dt, "name": "Foo"}

        self.cache.set("test_key", test_dict)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, dict)
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["name"], "Foo")
        self.assertEqual(res["date"], now_dt)

    def test_save_float(self):
        float_val = 1.345620002

        self.cache.set("test_key", float_val)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, float)
        self.assertEqual(res, float_val)

    def test_timeout(self):
        self.cache.set("test_key", 222, timeout=3)
        time.sleep(4)

        res = self.cache.get("test_key")
        self.assertIsNone(res)

    def test_timeout_0(self):
        self.cache.set("test_key", 222, timeout=0)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

    def test_timeout_parameter_as_positional_argument(self):
        self.cache.set("test_key", 222, -1)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

        self.cache.set("test_key", 222, 1)
        res1 = self.cache.get("test_key")
        time.sleep(2)
        res2 = self.cache.get("test_key")
        self.assertEqual(res1, 222)
        self.assertIsNone(res2)

        # nx=True should not overwrite expire of key already in db
        self.cache.set("test_key", 222, None)
        self.cache.set("test_key", 222, -1, nx=True)
        res = self.cache.get("test_key")
        self.assertEqual(res, 222)

    def test_timeout_negative(self):
        self.cache.set("test_key", 222, timeout=-1)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

        self.cache.set("test_key", 222, timeout=None)
        self.cache.set("test_key", 222, timeout=-1)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

        # nx=True should not overwrite expire of key already in db
        self.cache.set("test_key", 222, timeout=None)
        self.cache.set("test_key", 222, timeout=-1, nx=True)
        res = self.cache.get("test_key")
        self.assertEqual(res, 222)

    def test_timeout_tiny(self):
        self.cache.set("test_key", 222, timeout=0.00001)
        res = self.cache.get("test_key")
        self.assertIn(res, (None, 222))

    def test_set_add(self):
        self.cache.set("add_key", "Initial value")
        res = self.cache.add("add_key", "New value")
        self.assertIs(res, False)

        res = cache.get("add_key")
        self.assertEqual(res, "Initial value")
        res = self.cache.add("other_key", "New value")
        self.assertIs(res, True)

    def test_get_many(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"a": 1, "b": 2, "c": 3})

    def test_get_many_unicode(self):
        self.cache.set("a", "1")
        self.cache.set("b", "2")
        self.cache.set("c", "3")

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"a": "1", "b": "2", "c": "3"})

    def test_set_many(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"a": 1, "b": 2, "c": 3})

    def test_set_call_empty_pipeline(self):
        if isinstance(self.cache.client, ShardClient):
            self.skipTest("ShardClient doesn't support get_client")

        pipeline = self.cache.client.get_client(write=True).pipeline()
        key = "key"
        value = "value"

        with patch.object(pipeline, "set") as mocked_set:
            self.cache.set(key, value, client=pipeline)

        if isinstance(self.cache.client, herd.HerdClient):
            default_timeout = self.cache.client._backend.default_timeout
            herd_timeout = (default_timeout + herd.CACHE_HERD_TIMEOUT) * 1000
            herd_pack_value = self.cache.client._pack(value, default_timeout)
            mocked_set.assert_called_once_with(
                self.cache.client.make_key(key, version=None),
                self.cache.client.encode(herd_pack_value),
                nx=False,
                px=herd_timeout,
                xx=False,
            )
        else:
            mocked_set.assert_called_once_with(
                self.cache.client.make_key(key, version=None),
                self.cache.client.encode(value),
                nx=False,
                px=self.cache.client._backend.default_timeout * 1000,
                xx=False,
            )

    def test_delete(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete("a")
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"b": 2, "c": 3})

        res = self.cache.delete("a")
        self.assertFalse(bool(res))

    @patch("django_redis.cache.DJANGO_VERSION", (3, 1, 0, "final", 0))
    def test_delete_return_value_type_new31(self):
        """delete() returns a boolean instead of int since django version 3.1"""
        self.cache.set("a", 1)
        res = self.cache.delete("a")
        self.assertEqual(type(res), bool)
        self.assertTrue(res)
        res = self.cache.delete("b")
        self.assertEqual(type(res), bool)
        self.assertFalse(res)

    @patch("django_redis.cache.DJANGO_VERSION", (3, 0, 1, "final", 0))
    def test_delete_return_value_type_before31(self):
        """delete() returns a int before django version 3.1"""
        self.cache.set("a", 1)
        res = self.cache.delete("a")
        self.assertEqual(type(res), int)
        self.assertEqual(res, 1)
        res = self.cache.delete("b")
        self.assertEqual(type(res), int)
        self.assertEqual(res, 0)

    def test_delete_many(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete_many(["a", "b"])
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"c": 3})

        res = self.cache.delete_many(["a", "b"])
        self.assertFalse(bool(res))

    def test_delete_many_generator(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete_many(key for key in ["a", "b"])
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"c": 3})

        res = self.cache.delete_many(["a", "b"])
        self.assertFalse(bool(res))

    def test_delete_many_empty_generator(self):
        res = self.cache.delete_many(key for key in [])
        self.assertFalse(bool(res))

    def test_incr(self):
        if isinstance(self.cache.client, herd.HerdClient):
            self.skipTest("HerdClient doesn't support incr")

        self.cache.set("num", 1)

        self.cache.incr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 2)

        self.cache.incr("num", 10)
        res = self.cache.get("num")
        self.assertEqual(res, 12)

        # max 64 bit signed int
        self.cache.set("num", 9223372036854775807)

        self.cache.incr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775808)

        self.cache.incr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775810)

        self.cache.set("num", 3)

        self.cache.incr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, 5)

    def test_incr_no_timeout(self):
        if isinstance(self.cache.client, herd.HerdClient):
            self.skipTest("HerdClient doesn't support incr")

        self.cache.set("num", 1, timeout=None)

        self.cache.incr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 2)

        self.cache.incr("num", 10)
        res = self.cache.get("num")
        self.assertEqual(res, 12)

        # max 64 bit signed int
        self.cache.set("num", 9223372036854775807, timeout=None)

        self.cache.incr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775808)

        self.cache.incr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775810)

        self.cache.set("num", 3, timeout=None)

        self.cache.incr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, 5)

    def test_incr_error(self):
        if isinstance(self.cache.client, herd.HerdClient):
            self.skipTest("HerdClient doesn't support incr")

        with self.assertRaises(ValueError):
            # key does not exist
            self.cache.incr("numnum")

    def test_incr_ignore_check(self):
        if isinstance(self.cache.client, ShardClient):
            self.skipTest(
                "ShardClient doesn't support argument ignore_key_check to incr"
            )
        if isinstance(self.cache.client, herd.HerdClient):
            self.skipTest("HerdClient doesn't support incr")

        # key exists check will be skipped and the value will be incremented by
        # '1' which is the default delta
        self.cache.incr("num", ignore_key_check=True)
        res = self.cache.get("num")
        self.assertEqual(res, 1)
        self.cache.delete("num")

        # since key doesnt exist it is set to the delta value, 10 in this case
        self.cache.incr("num", 10, ignore_key_check=True)
        res = self.cache.get("num")
        self.assertEqual(res, 10)
        self.cache.delete("num")

        # following are just regression checks to make sure it still works as
        # expected with incr max 64 bit signed int
        self.cache.set("num", 9223372036854775807)

        self.cache.incr("num", ignore_key_check=True)
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775808)

        self.cache.incr("num", 2, ignore_key_check=True)
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775810)

        self.cache.set("num", 3)

        self.cache.incr("num", 2, ignore_key_check=True)
        res = self.cache.get("num")
        self.assertEqual(res, 5)

    def test_get_set_bool(self):
        self.cache.set("bool", True)
        res = self.cache.get("bool")

        self.assertIsInstance(res, bool)
        self.assertIs(res, True)

        self.cache.set("bool", False)
        res = self.cache.get("bool")

        self.assertIsInstance(res, bool)
        self.assertIs(res, False)

    def test_decr(self):
        if isinstance(self.cache.client, herd.HerdClient):
            self.skipTest("HerdClient doesn't support decr")

        self.cache.set("num", 20)

        self.cache.decr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 19)

        self.cache.decr("num", 20)
        res = self.cache.get("num")
        self.assertEqual(res, -1)

        self.cache.decr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, -3)

        self.cache.set("num", 20)

        self.cache.decr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 19)

        # max 64 bit signed int + 1
        self.cache.set("num", 9223372036854775808)

        self.cache.decr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775807)

        self.cache.decr("num", 2)
        res = self.cache.get("num")
        self.assertEqual(res, 9223372036854775805)

    def test_version(self):
        self.cache.set("keytest", 2, version=2)
        res = self.cache.get("keytest")
        self.assertIsNone(res)

        res = self.cache.get("keytest", version=2)
        self.assertEqual(res, 2)

    def test_incr_version(self):
        self.cache.set("keytest", 2)
        self.cache.incr_version("keytest")

        res = self.cache.get("keytest")
        self.assertIsNone(res)

        res = self.cache.get("keytest", version=2)
        self.assertEqual(res, 2)

    def test_ttl_incr_version_no_timeout(self):
        self.cache.set("my_key", "hello world!", timeout=None)

        self.cache.incr_version("my_key")

        my_value = self.cache.get("my_key", version=2)

        self.assertEqual(my_value, "hello world!")

    def test_delete_pattern(self):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), {"foo-bb", "foo-bc"})

        res = self.cache.delete_pattern("*foo-a*")
        self.assertFalse(bool(res))

    @patch("django_redis.cache.RedisCache.client")
    def test_delete_pattern_with_custom_count(self, client_mock):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        self.cache.delete_pattern("*foo-a*", itersize=2)

        client_mock.delete_pattern.assert_called_once_with("*foo-a*", itersize=2)

    @patch("django_redis.cache.RedisCache.client")
    def test_delete_pattern_with_settings_default_scan_count(self, client_mock):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")
        expected_count = django_redis.cache.DJANGO_REDIS_SCAN_ITERSIZE

        self.cache.delete_pattern("*foo-a*")

        client_mock.delete_pattern.assert_called_once_with(
            "*foo-a*", itersize=expected_count
        )

    @override_settings(DJANGO_REDIS_CLOSE_CONNECTION=True)
    def test_close(self):
        self.cache.set("f", "1")
        self.cache.close()

    def test_close_client(self):
        with patch.object(self.cache.client, "close") as mock:
            self.cache.close()
            assert mock.called

    def test_ttl(self):
        self.cache.set("foo", "bar", 10)
        ttl = self.cache.ttl("foo")

        if isinstance(self.cache.client, herd.HerdClient):
            self.assertAlmostEqual(ttl, 12)
        else:
            self.assertAlmostEqual(ttl, 10)

        # Test ttl None
        self.cache.set("foo", "foo", timeout=None)
        ttl = self.cache.ttl("foo")
        self.assertIsNone(ttl)

        # Test ttl with expired key
        self.cache.set("foo", "foo", timeout=-1)
        ttl = self.cache.ttl("foo")
        self.assertEqual(ttl, 0)

        # Test ttl with not existent key
        ttl = self.cache.ttl("not-existent-key")
        self.assertEqual(ttl, 0)

    def test_pttl(self):

        # Test pttl
        self.cache.set("foo", "bar", 10)
        ttl = self.cache.pttl("foo")

        # delta is set to 10 as precision error causes tests to fail
        if isinstance(self.cache.client, herd.HerdClient):
            self.assertAlmostEqual(ttl, 12000, delta=10)
        else:
            self.assertAlmostEqual(ttl, 10000, delta=10)

        # Test pttl with float value
        self.cache.set("foo", "bar", 5.5)
        ttl = self.cache.pttl("foo")

        if isinstance(cache.client, herd.HerdClient):
            self.assertAlmostEqual(ttl, 7500, delta=10)
        else:
            self.assertAlmostEqual(ttl, 5500, delta=10)

        # Test pttl None
        self.cache.set("foo", "foo", timeout=None)
        ttl = self.cache.pttl("foo")
        self.assertIsNone(ttl)

        # Test pttl with expired key
        self.cache.set("foo", "foo", timeout=-1)
        ttl = self.cache.pttl("foo")
        self.assertEqual(ttl, 0)

        # Test pttl with not existent key
        ttl = self.cache.pttl("not-existent-key")
        self.assertEqual(ttl, 0)

    def test_persist(self):
        self.cache.set("foo", "bar", timeout=20)
        self.cache.persist("foo")

        ttl = self.cache.ttl("foo")
        self.assertIsNone(ttl)

    def test_expire(self):
        self.cache.set("foo", "bar", timeout=None)
        self.cache.expire("foo", 20)
        ttl = self.cache.ttl("foo")
        self.assertAlmostEqual(ttl, 20)

    def test_pexpire(self):
        self.cache.set("foo", "bar", timeout=None)
        self.cache.pexpire("foo", 20500)
        ttl = self.cache.pttl("foo")
        # delta is set to 10 as precision error causes tests to fail
        self.assertAlmostEqual(ttl, 20500, delta=10)

    def test_expire_at(self):

        # Test settings expiration time 1 hour ahead by datetime.
        self.cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=1)
        self.cache.expire_at("foo", expiration_time)
        ttl = self.cache.ttl("foo")
        self.assertAlmostEqual(ttl, timedelta(hours=1).total_seconds(), delta=1)

        # Test settings expiration time 1 hour ahead by Unix timestamp.
        self.cache.set("foo", "bar", timeout=None)
        expiration_time = datetime.datetime.now() + timedelta(hours=2)
        self.cache.expire_at("foo", int(expiration_time.timestamp()))
        ttl = self.cache.ttl("foo")
        self.assertAlmostEqual(ttl, timedelta(hours=1).total_seconds() * 2, delta=1)

        # Test settings expiration time 1 hour in past, which effectively
        # deletes the key.
        expiration_time = datetime.datetime.now() - timedelta(hours=2)
        self.cache.expire_at("foo", expiration_time)
        value = self.cache.get("foo")
        self.assertIsNone(value)

    def test_lock(self):
        lock = self.cache.lock("foobar")
        lock.acquire(blocking=True)

        self.assertTrue(self.cache.has_key("foobar"))
        lock.release()
        self.assertFalse(self.cache.has_key("foobar"))

    def test_lock_released_by_thread(self):
        lock = self.cache.lock("foobar", thread_local=False)
        lock.acquire(blocking=True)

        def release_lock(lock_):
            lock_.release()

        t = threading.Thread(target=release_lock, args=[lock])
        t.start()
        t.join()

        self.assertFalse(self.cache.has_key("foobar"))

    def test_iter_keys(self):
        cache = caches["default"]
        if isinstance(cache.client, ShardClient):
            self.skipTest("ShardClient doesn't support iter_keys")

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test simple result
        result = set(cache.iter_keys("foo*"))
        self.assertEqual(result, {"foo1", "foo2", "foo3"})

        # Test limited result
        result = list(cache.iter_keys("foo*", itersize=2))
        self.assertEqual(len(result), 3)

        # Test generator object
        result = cache.iter_keys("foo*")
        self.assertNotEqual(next(result), None)

    def test_primary_replica_switching(self):
        if isinstance(self.cache.client, ShardClient):
            self.skipTest("ShardClient doesn't support get_client")

        cache = caches["sample"]
        client = cache.client
        client._server = ["foo", "bar"]
        client._clients = ["Foo", "Bar"]

        self.assertEqual(client.get_client(write=True), "Foo")
        self.assertEqual(client.get_client(write=False), "Bar")

    def test_touch_zero_timeout(self):
        self.cache.set("test_key", 222, timeout=10)

        self.assertIs(self.cache.touch("test_key", 0), True)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

    def test_touch_positive_timeout(self):
        self.cache.set("test_key", 222, timeout=10)

        self.assertIs(self.cache.touch("test_key", 2), True)
        self.assertEqual(self.cache.get("test_key"), 222)
        time.sleep(3)
        self.assertIsNone(self.cache.get("test_key"))

    def test_touch_negative_timeout(self):
        self.cache.set("test_key", 222, timeout=10)

        self.assertIs(self.cache.touch("test_key", -1), True)
        res = self.cache.get("test_key")
        self.assertIsNone(res)

    def test_touch_missed_key(self):
        self.assertIs(self.cache.touch("test_key_does_not_exist", 1), False)

    def test_touch_forever(self):
        self.cache.set("test_key", "foo", timeout=1)
        result = self.cache.touch("test_key", None)
        self.assertIs(result, True)
        self.assertIsNone(self.cache.ttl("test_key"))
        time.sleep(2)
        self.assertEqual(self.cache.get("test_key"), "foo")

    def test_touch_forever_nonexistent(self):
        result = self.cache.touch("test_key_does_not_exist", None)
        self.assertIs(result, False)

    def test_touch_default_timeout(self):
        self.cache.set("test_key", "foo", timeout=1)
        result = self.cache.touch("test_key")
        self.assertIs(result, True)
        time.sleep(2)
        self.assertEqual(self.cache.get("test_key"), "foo")

    def test_clear(self):
        self.cache.set("foo", "bar")
        value_from_cache = self.cache.get("foo")
        self.assertEqual(value_from_cache, "bar")
        self.cache.clear()
        value_from_cache_after_clear = self.cache.get("foo")
        self.assertIsNone(value_from_cache_after_clear)


class DjangoOmitExceptionsTests(unittest.TestCase):
    def setUp(self):
        caches_setting = copy.deepcopy(settings.CACHES)
        caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
        cm = override_settings(
            CACHES=caches_setting, DJANGO_REDIS_IGNORE_EXCEPTIONS=True
        )
        cm.enable()
        self.addCleanup(cm.disable)
        self.cache = caches["doesnotexist"]

    def test_get_many_returns_default_arg(self):
        self.assertIs(self.cache._ignore_exceptions, True)
        self.assertEqual(self.cache.get_many(["key1", "key2", "key3"]), {})

    def test_get(self):
        self.assertIs(self.cache._ignore_exceptions, True)
        self.assertIsNone(self.cache.get("key"))
        self.assertEqual(self.cache.get("key", "default"), "default")
        self.assertEqual(self.cache.get("key", default="default"), "default")


class DjangoOmitExceptionsPriority1Tests(unittest.TestCase):
    def setUp(self):
        caches_setting = copy.deepcopy(settings.CACHES)
        caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
        cm = override_settings(
            CACHES=caches_setting, DJANGO_REDIS_IGNORE_EXCEPTIONS=False
        )
        cm.enable()
        self.addCleanup(cm.disable)
        self.cache = caches["doesnotexist"]

    def test_get(self):
        self.assertIs(self.cache._ignore_exceptions, True)
        self.assertIsNone(self.cache.get("key"))


class DjangoOmitExceptionsPriority2Tests(unittest.TestCase):
    def setUp(self):
        caches_setting = copy.deepcopy(settings.CACHES)
        caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = False
        cm = override_settings(
            CACHES=caches_setting, DJANGO_REDIS_IGNORE_EXCEPTIONS=True
        )
        cm.enable()
        self.addCleanup(cm.disable)
        self.cache = caches["doesnotexist"]

    def test_get(self):
        self.assertIs(self.cache._ignore_exceptions, False)
        with self.assertRaises(ConnectionError):
            self.cache.get("key")


# Copied from Django's sessions test suite. Keep in sync with upstream.
# https://github.com/django/django/blob/main/tests/sessions_tests/tests.py
class SessionTestsMixin:
    # This does not inherit from TestCase to avoid any tests being run with this
    # class, which wouldn't work, and to allow different TestCase subclasses to
    # be used.

    backend = None  # subclasses must specify

    def setUp(self):
        self.session = self.backend()

    def tearDown(self):
        # NB: be careful to delete any sessions created; stale sessions fill up
        # the /tmp (with some backends) and eventually overwhelm it after lots
        # of runs (think buildbots)
        self.session.delete()

    def test_new_session(self):
        self.assertIs(self.session.modified, False)
        self.assertIs(self.session.accessed, False)

    def test_get_empty(self):
        self.assertIsNone(self.session.get("cat"))

    def test_store(self):
        self.session["cat"] = "dog"
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.pop("cat"), "dog")

    def test_pop(self):
        self.session["some key"] = "exists"
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(self.session.pop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(self.session.get("some key"))

    def test_pop_default(self):
        self.assertEqual(
            self.session.pop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_default_named_argument(self):
        self.assertEqual(
            self.session.pop("some key", default="does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_no_default_keyerror_raised(self):
        with self.assertRaises(KeyError):
            self.session.pop("some key")

    def test_setdefault(self):
        self.assertEqual(self.session.setdefault("foo", "bar"), "bar")
        self.assertEqual(self.session.setdefault("foo", "baz"), "bar")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_update(self):
        self.session.update({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.get("update key"), 1)

    def test_has_key(self):
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn("some key", self.session)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_values(self):
        self.assertEqual(list(self.session.values()), [])
        self.assertIs(self.session.accessed, True)
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.values()), [1])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_keys(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_clear(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.session.clear()
        self.assertEqual(list(self.session.items()), [])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_save(self):
        self.session.save()
        self.assertIs(self.session.exists(self.session.session_key), True)

    def test_delete(self):
        self.session.save()
        self.session.delete(self.session.session_key)
        self.assertIs(self.session.exists(self.session.session_key), False)

    def test_flush(self):
        self.session["foo"] = "bar"
        self.session.save()
        prev_key = self.session.session_key
        self.session.flush()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertIsNone(self.session.session_key)
        self.assertIs(self.session.modified, True)
        self.assertIs(self.session.accessed, True)

    def test_cycle(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_key = self.session.session_key
        prev_data = list(self.session.items())
        self.session.cycle_key()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertEqual(list(self.session.items()), prev_data)

    def test_cycle_with_no_session_cache(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_data = self.session.items()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        self.session.cycle_key()
        self.assertCountEqual(self.session.items(), prev_data)

    def test_save_doesnt_clear_data(self):
        self.session["a"] = "b"
        self.session.save()
        self.assertEqual(self.session["a"], "b")

    def test_invalid_key(self):
        # Submitting an invalid session key (either by guessing, or if the db has
        # removed the key) results in a new key being generated.
        try:
            session = self.backend("1")
            session.save()
            self.assertNotEqual(session.session_key, "1")
            self.assertIsNone(session.get("cat"))
            session.delete()
        finally:
            # Some backends leave a stale cache entry for the invalid
            # session key; make sure that entry is manually deleted
            session.delete("1")

    def test_session_key_empty_string_invalid(self):
        """Falsey values (Such as an empty string) are rejected."""
        self.session._session_key = ""
        self.assertIsNone(self.session.session_key)

    def test_session_key_too_short_invalid(self):
        """Strings shorter than 8 characters are rejected."""
        self.session._session_key = "1234567"
        self.assertIsNone(self.session.session_key)

    def test_session_key_valid_string_saved(self):
        """Strings of length 8 and up are accepted and stored."""
        self.session._session_key = "12345678"
        self.assertEqual(self.session.session_key, "12345678")

    def test_session_key_is_read_only(self):
        def set_session_key(session):
            session.session_key = session._get_new_session_key()

        with self.assertRaises(AttributeError):
            set_session_key(self.session)

    # Custom session expiry
    def test_default_expiry(self):
        # A normal session has a max age equal to settings
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

        # So does a custom session with an idle expiration time of 0 (but it'll
        # expire at browser close)
        self.session.set_expiry(0)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_custom_expiry_seconds(self):
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
        modification = timezone.now()

        # Mock timezone.now, because set_expiry calls it on this code path.
        original_now = timezone.now
        try:
            timezone.now = lambda: modification
            self.session.set_expiry(timedelta(seconds=10))
        finally:
            timezone.now = original_now

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_datetime(self):
        modification = timezone.now()

        self.session.set_expiry(modification + timedelta(seconds=10))

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_reset(self):
        self.session.set_expiry(None)
        self.session.set_expiry(10)
        self.session.set_expiry(None)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_get_expire_at_browser_close(self):
        # Tests get_expire_at_browser_close with different settings and different
        # set_expiry calls
        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=False):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

    def test_decode(self):
        # Ensure we can decode what we encode
        data = {"a test key": "a test value"}
        encoded = self.session.encode(data)
        self.assertEqual(self.session.decode(encoded), data)

    def test_decode_failure_logged_to_security(self):
        bad_encode = base64.b64encode(b"flaskdj:alkdjf").decode("ascii")
        with self.assertLogs("django.security.SuspiciousSession", "WARNING") as cm:
            self.assertEqual({}, self.session.decode(bad_encode))
        # The failed decode is logged.
        self.assertIn("corrupted", cm.output[0])

    def test_actual_expiry(self):
        # this doesn't work with JSONSerializer (serializing timedelta)
        with override_settings(
            SESSION_SERIALIZER="django.contrib.sessions.serializers.PickleSerializer"
        ):
            self.session = self.backend()  # reinitialize after overriding settings

            # Regression test for #19200
            old_session_key = None
            new_session_key = None
            try:
                self.session["foo"] = "bar"
                self.session.set_expiry(-timedelta(seconds=10))
                self.session.save()
                old_session_key = self.session.session_key
                # With an expiry date in the past, the session expires instantly.
                new_session = self.backend(self.session.session_key)
                new_session_key = new_session.session_key
                self.assertNotIn("foo", new_session)
            finally:
                self.session.delete(old_session_key)
                self.session.delete(new_session_key)

    def test_session_load_does_not_create_record(self):
        """
        Loading an unknown session key does not create a session record.

        Creating session records on load is a DOS vulnerability.
        """
        session = self.backend("someunknownkey")
        session.load()

        self.assertIsNone(session.session_key)
        self.assertIs(session.exists(session.session_key), False)
        # provided unknown key was cycled, not reused
        self.assertNotEqual(session.session_key, "someunknownkey")

    def test_session_save_does_not_resurrect_session_logged_out_in_other_context(self):
        """
        Sessions shouldn't be resurrected by a concurrent request.
        """
        from django.contrib.sessions.backends.base import UpdateError

        # Create new session.
        s1 = self.backend()
        s1["test_data"] = "value1"
        s1.save(must_create=True)

        # Logout in another context.
        s2 = self.backend(s1.session_key)
        s2.delete()

        # Modify session in first context.
        s1["test_data"] = "value2"
        with self.assertRaises(UpdateError):
            # This should throw an exception as the session is deleted, not
            # resurrect the session.
            s1.save()

        self.assertEqual(s1.load(), {})


class SessionTests(SessionTestsMixin, unittest.TestCase):
    backend = CacheSession

    def test_actual_expiry(self):
        if isinstance(
            caches[DEFAULT_CACHE_ALIAS].client._serializer, MSGPackSerializer
        ):
            self.skipTest("msgpack serializer doesn't support datetime serialization")
        super().test_actual_expiry()


class TestClientClose(unittest.TestCase):
    def setUp(self):
        self.client = caches[DEFAULT_CACHE_ALIAS].client
        self.client.set("TestClientClose", 0)

    def tearDown(self):
        self.client.delete("TestClientClose")
        self.client.clear()

    def test_close_client_disconnect_default(self):
        with patch.object(self.client.connection_factory, "disconnect") as mock:
            self.client.close()
            assert not mock.called

    @override_settings(DJANGO_REDIS_CLOSE_CONNECTION=True)
    def test_close_disconnect_settings(self):
        with patch.object(self.client.connection_factory, "disconnect") as mock:
            self.client.close()
            assert mock.called

    def test_close_disconnect_settings_cache(self):
        settings.CACHES[DEFAULT_CACHE_ALIAS]["OPTIONS"]["CLOSE_CONNECTION"] = True
        with override_settings(CACHES=settings.CACHES):
            # enabling override_settings context emits 'setting_changed' signal
            # (re-set the value to populate again client connections)
            self.client.set("TestClientClose", 0)
            with patch.object(self.client.connection_factory, "disconnect") as mock:
                self.client.close()
                assert mock.called

    def test_close_disconnect_client_options(self):
        self.client._options["CLOSE_CONNECTION"] = True
        with patch.object(self.client.connection_factory, "disconnect") as mock:
            self.client.close()
            assert mock.called


class TestDefaultClient(unittest.TestCase):
    @patch("test_backend.DefaultClient.get_client")
    @patch("test_backend.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_get_client_given_no_client(
        self, init_mock, get_client_mock
    ):
        client = DefaultClient()
        client._backend = Mock()
        client._backend.key_prefix = ""

        client.delete_pattern(pattern="foo*")
        get_client_mock.assert_called_once_with(write=True)

    @patch("test_backend.DefaultClient.make_pattern")
    @patch("test_backend.DefaultClient.get_client", return_value=Mock())
    @patch("test_backend.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_make_pattern(
        self, init_mock, get_client_mock, make_pattern_mock
    ):
        client = DefaultClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*")

        kwargs = {"version": None, "prefix": None}
        # if not isinstance(caches['default'].client, ShardClient):
        # kwargs['prefix'] = None

        make_pattern_mock.assert_called_once_with("foo*", **kwargs)

    @patch("test_backend.DefaultClient.make_pattern")
    @patch("test_backend.DefaultClient.get_client", return_value=Mock())
    @patch("test_backend.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
        self, init_mock, get_client_mock, make_pattern_mock
    ):
        client = DefaultClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*", itersize=90210)

        get_client_mock.return_value.scan_iter.assert_called_once_with(
            count=90210, match=make_pattern_mock.return_value
        )


class TestShardClient(unittest.TestCase):
    @patch("test_backend.DefaultClient.make_pattern")
    @patch("test_backend.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
        self, init_mock, make_pattern_mock
    ):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""

        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*", itersize=10)

        connection.scan_iter.assert_called_once_with(
            count=10, match=make_pattern_mock.return_value
        )

    @patch("test_backend.DefaultClient.make_pattern")
    @patch("test_backend.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter(self, init_mock, make_pattern_mock):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.scan_iter.assert_called_once_with(
            match=make_pattern_mock.return_value
        )

    @patch("test_backend.DefaultClient.make_pattern")
    @patch("test_backend.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_delete_for_given_keys(
        self, init_mock, make_pattern_mock
    ):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        connection = Mock()
        connection.scan_iter.return_value = [Mock(), Mock()]
        connection.delete.return_value = 0
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.delete.assert_called_once_with(*connection.scan_iter.return_value)
