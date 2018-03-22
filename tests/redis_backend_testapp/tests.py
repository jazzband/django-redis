# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals, print_function

import sys
import time
import datetime

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from django.conf import settings
from django.core.cache import cache, caches
from django.test import TestCase

import django_redis.cache
from django_redis import pool
from django_redis.client import herd

herd.CACHE_HERD_TIMEOUT = 2

if sys.version_info[0] < 3:
    text_type = unicode
    bytes_type = str
else:
    text_type = str
    bytes_type = bytes
    long = int


def make_key(key, prefix, version):
    return "{}#{}#{}".format(prefix, version, key)

def reverse_key(key):
    return key.split("#", 2)[2]


class DjangoRedisConnectionStrings(TestCase):
    def setUp(self):
        self.cf = pool.get_connection_factory(options={})
        self.constring1 = "127.0.0.1:6379:1"
        self.constring2 = "localhost:6379:2"
        self.constring3 = "unix:/tmp/foo.bar:2"
        self.constring4 = "unix://tmp/foo.bar?db=1"
        self.constring5 = "redis://localhost/2"
        self.constring6 = "rediss://localhost:3333?db=2"

    def test_old_connection_strings_detection(self):
        with patch.object(pool.ConnectionFactory, "adapt_old_url_format") as mc:
            mc.return_value = {"url": "/foo/bar"}
            res1 = self.cf.make_connection_params(self.constring1)
            res2 = self.cf.make_connection_params(self.constring2)
            res3 = self.cf.make_connection_params(self.constring3)
            res4 = self.cf.make_connection_params(self.constring4)
            res5 = self.cf.make_connection_params(self.constring5)
            res6 = self.cf.make_connection_params(self.constring6)

            self.assertEqual(mc.call_count, 3)

    def test_old_connection_strings(self):
        res1 = self.cf.adapt_old_url_format(self.constring1)
        res2 = self.cf.adapt_old_url_format(self.constring2)
        res3 = self.cf.adapt_old_url_format(self.constring3)

        self.assertEqual(res1, "redis://127.0.0.1:6379?db=1")
        self.assertEqual(res2, "redis://localhost:6379?db=2")
        self.assertEqual(res3, "unix:///tmp/foo.bar?db=2")

    def test_new_connection_strings(self):
        res1 = self.cf.make_connection_params(self.constring4)
        res2 = self.cf.make_connection_params(self.constring5)
        res3 = self.cf.make_connection_params(self.constring6)

        self.assertEqual(res1["url"], self.constring4)
        self.assertEqual(res2["url"], self.constring5)
        self.assertEqual(res3["url"], self.constring6)

class DjangoRedisCacheTestCustomKeyFunction(TestCase):
    def setUp(self):
        self.old_kf = settings.CACHES['default'].get('KEY_FUNCTION')
        self.old_rkf = settings.CACHES['default'].get('REVERSE_KEY_FUNCTION')
        settings.CACHES['default']['KEY_FUNCTION'] = 'redis_backend_testapp.tests.make_key'
        settings.CACHES['default']['REVERSE_KEY_FUNCTION'] = 'redis_backend_testapp.tests.reverse_key'

        self.cache = caches['default']
        try:
            self.cache.clear()
        except Exception:
            pass

    def test_custom_key_function(self):
        for key in ["foo-aa","foo-ab", "foo-bb","foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), set(["foo-bb","foo-bc"]))
        # ensure our custom function was actually called
        try:
            self.assertEqual(set(k.decode('utf-8') for k in self.cache.raw_client.keys('*')),
                set(['#1#foo-bc', '#1#foo-bb']))
        except (NotImplementedError, AttributeError):
            # not all clients support .keys()
            pass

    def tearDown(self):
        settings.CACHES['default']['KEY_FUNCTION'] = self.old_kf
        settings.CACHES['default']['REVERSE_KEY_FUNCTION'] = self.old_rkf


class DjangoRedisCacheTests(TestCase):
    def setUp(self):
        self.cache = cache

        try:
            self.cache.clear()
        except Exception:
            pass

    def test_setnx(self):
        # we should ensure there is no test_key_nx in redis
        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx", None)
        self.assertEqual(res, None)

        res = self.cache.set("test_key_nx", 1, nx=True)
        self.assertTrue(res)
        # test that second set will have
        res = self.cache.set("test_key_nx", 2, nx=True)
        self.assertFalse(res)
        res = self.cache.get("test_key_nx")
        self.assertEqual(res, 1)

        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx", None)
        self.assertEqual(res, None)

    def test_setnx_timeout(self):
        # test that timeout still works for nx=True
        res = self.cache.set("test_key_nx", 1, timeout=2, nx=True)
        self.assertTrue(res)
        time.sleep(3)
        res = self.cache.get("test_key_nx", None)
        self.assertEqual(res, None)

        # test that timeout will not affect key, if it was there
        self.cache.set("test_key_nx", 1)
        res = self.cache.set("test_key_nx", 2, timeout=2, nx=True)
        self.assertFalse(res)
        time.sleep(3)
        res = self.cache.get("test_key_nx", None)
        self.assertEqual(res, 1)

        self.cache.delete("test_key_nx")
        res = self.cache.get("test_key_nx", None)
        self.assertEqual(res, None)

    def test_save_and_integer(self):
        self.cache.set("test_key", 2)
        res = self.cache.get("test_key", "Foo")

        self.assertIsInstance(res, int)
        self.assertEqual(res, 2)

    def test_save_string(self):
        self.cache.set("test_key", "hello")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, text_type)
        self.assertEqual(res, "hello")

        self.cache.set("test_key", "2")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, text_type)
        self.assertEqual(res, "2")

    def test_save_unicode(self):
        self.cache.set("test_key", "heló")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, text_type)
        self.assertEqual(res, "heló")

    def test_save_dict(self):
        now_dt = datetime.datetime.now()
        test_dict = {"id":1, "date": now_dt, "name": "Foo"}

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

        res = self.cache.get("test_key", None)
        self.assertEqual(res, None)

    def test_timeout_0(self):
        self.cache.set("test_key", 222, timeout=0)
        res = self.cache.get("test_key", None)
        self.assertEqual(res, 222)

    def test_timeout_parameter_as_positional_argument(self):
        self.cache.set("test_key", 222, -1)
        res = self.cache.get("test_key", None)
        self.assertIsNone(res)

        self.cache.set("test_key", 222, 1)
        res1 = self.cache.get("test_key", None)
        time.sleep(2)
        res2 = self.cache.get("test_key", None)
        self.assertEqual(res1, 222)
        self.assertEqual(res2, None)

        # nx=True should not overwrite expire of key already in db
        self.cache.set("test_key", 222, 0)
        self.cache.set("test_key", 222, -1, nx=True)
        res = self.cache.get("test_key", None)
        self.assertEqual(res, 222)

    def test_timeout_negative(self):
        self.cache.set("test_key", 222, timeout=-1)
        res = self.cache.get("test_key", None)
        self.assertIsNone(res)

        self.cache.set("test_key", 222, timeout=0)
        self.cache.set("test_key", 222, timeout=-1)
        res = self.cache.get("test_key", None)
        self.assertIsNone(res)

        # nx=True should not overwrite expire of key already in db
        self.cache.set("test_key", 222, timeout=0)
        self.cache.set("test_key", 222, timeout=-1, nx=True)
        res = self.cache.get("test_key", None)
        self.assertEqual(res, 222)

    def test_set_add(self):
        self.cache.set("add_key", "Initial value")
        self.cache.add("add_key", "New value")
        res = cache.get("add_key")

        self.assertEqual(res, "Initial value")

    def test_get_many(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)

        res = self.cache.get_many(["a","b","c"])
        self.assertEqual(res, {"a": 1, "b": 2, "c": 3})

    def test_get_many_unicode(self):
        self.cache.set("a", "1")
        self.cache.set("b", "2")
        self.cache.set("c", "3")

        res = self.cache.get_many(["a","b","c"])
        self.assertEqual(res, {"a": "1", "b": "2", "c": "3"})

    def test_set_many(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"a": 1, "b": 2, "c": 3})

    def test_delete(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete("a")
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"b": 2, "c": 3})

        res = self.cache.delete("a")
        self.assertFalse(bool(res))

    def test_delete_many(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete_many(["a","b"])
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"c": 3})

        res = self.cache.delete_many(["a","b"])
        self.assertFalse(bool(res))

    def test_incr(self):
        try:
            self.cache.set("num", 1)

            self.cache.incr("num")
            res = self.cache.get("num")
            self.assertEqual(res, 2)

            self.cache.incr("num", 10)
            res = self.cache.get("num")
            self.assertEqual(res, 12)

            #max 64 bit signed int
            self.cache.set("num", 9223372036854775807)

            self.cache.incr("num")
            res = self.cache.get("num")
            self.assertEqual(res, 9223372036854775808)

            self.cache.incr("num", 2)
            res = self.cache.get("num")
            self.assertEqual(res, 9223372036854775810)

            self.cache.set("num", long(3))

            self.cache.incr("num", 2)
            res = self.cache.get("num")
            self.assertEqual(res, 5)

        except NotImplementedError as e:
            print(e)

    def test_get_set_bool(self):
        self.cache.set("bool", True)
        res = self.cache.get("bool")

        self.assertIsInstance(res, bool)
        self.assertEqual(res, True)

        self.cache.set("bool", False)
        res = self.cache.get("bool")

        self.assertIsInstance(res, bool)
        self.assertEqual(res, False)

    def test_decr(self):
        try:
            self.cache.set("num", 20)

            self.cache.decr("num")
            res = self.cache.get("num")
            self.assertEqual(res, 19)

            self.cache.decr("num", 20)
            res = self.cache.get("num")
            self.assertEqual(res, -1)

            self.cache.decr("num", long(2))
            res = self.cache.get("num")
            self.assertEqual(res, -3)

            self.cache.set("num", long(20))

            self.cache.decr("num")
            res = self.cache.get("num")
            self.assertEqual(res, 19)

            #max 64 bit signed int + 1
            self.cache.set("num", 9223372036854775808)

            self.cache.decr("num")
            res = self.cache.get("num")
            self.assertEqual(res, 9223372036854775807)

            self.cache.decr("num", 2)
            res = self.cache.get("num")
            self.assertEqual(res, 9223372036854775805)
        except NotImplementedError as e:
            print(e)

    def test_version(self):
        self.cache.set("keytest", 2, version=2)
        res = self.cache.get("keytest")
        self.assertEqual(res, None)

        res = self.cache.get("keytest", version=2)
        self.assertEqual(res, 2)

    def test_incr_version(self):
        try:
            self.cache.set("keytest", 2)
            self.cache.incr_version("keytest")

            res = self.cache.get("keytest")
            self.assertEqual(res, None)

            res = self.cache.get("keytest", version=2)
            self.assertEqual(res, 2)
        except NotImplementedError as e:
            print(e)

    def test_delete_pattern(self):
        for key in ["foo-aa","foo-ab", "foo-bb","foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), set(["foo-bb","foo-bc"]))

        res = self.cache.delete_pattern("*foo-a*")
        self.assertFalse(bool(res))

    def test_close(self):
        cache = caches["default"]
        cache.set("f", "1")
        cache.close()

    def test_ttl(self):
        cache = caches["default"]
        _params = cache._params
        _is_herd = (_params["OPTIONS"]["CLIENT_CLASS"] ==
                    "django_redis.client.HerdClient")
        _is_shard = (_params["OPTIONS"]["CLIENT_CLASS"] ==
                    "django_redis.client.ShardClient")

        # Not supported for shard client.
        if _is_shard:
            return

        # Test ttl
        cache.set("foo", "bar", 10)
        ttl = cache.ttl("foo")

        if _is_herd:
            self.assertAlmostEqual(ttl, 12)
        else:
            self.assertAlmostEqual(ttl, 10)

        # Test ttl None
        cache.set("foo", "foo", timeout=None)
        ttl = cache.ttl("foo")
        self.assertEqual(ttl, None)

        # Test ttl with expired key
        cache.set("foo", "foo", timeout=-1)
        ttl = cache.ttl("foo")

        # Test ttl with not existent key
        ttl = cache.ttl("not-existent-key")
        self.assertEqual(ttl, 0)

    def test_iter_keys(self):
        cache = caches["default"]
        _params = cache._params
        _is_shard = (_params["OPTIONS"]["CLIENT_CLASS"] ==
                    "django_redis.client.ShardClient")

        if _is_shard:
            return

        cache.set("foo1", 1)
        cache.set("foo2", 1)
        cache.set("foo3", 1)

        # Test simple result
        result = set(cache.iter_keys("foo*"))
        self.assertEqual(result, set(["foo1", "foo2", "foo3"]))

        # Test limited result
        result = list(cache.iter_keys("foo*", itersize=2))
        self.assertEqual(len(result), 3)

        # Test generator object
        result = cache.iter_keys("foo*")
        self.assertNotEqual(next(result), None)

    def test_master_slave_switching(self):
        try:
            cache = caches["sample"]
            client = cache.client
            client._server = ["foo", "bar",]
            client._clients = ["Foo", "Bar"]

            self.assertEqual(client.get_client(write=True), "Foo")
            self.assertEqual(client.get_client(write=False), "Bar")
        except NotImplementedError:
            pass


import django_redis.cache

class DjangoOmitExceptionsTests(TestCase):
    def setUp(self):
        self._orig_setting = django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS
        django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
        self.cache = caches["doesnotexist"]

    def tearDown(self):
        django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS = self._orig_setting

    def test_get(self):
        self.assertIsNone(self.cache.get("key"))
        self.assertEqual(self.cache.get("key", "default"), "default")
        self.assertEqual(self.cache.get("key", default="default"), "default")


from django.contrib.sessions.backends.cache import SessionStore as CacheSession

try:
    # SessionTestsMixin isn't available for import on django >= 1.8
    from django.contrib.sessions.tests import SessionTestsMixin
except ImportError:
    class SessionTestsMixin(object): pass



class SessionTests(SessionTestsMixin, TestCase):
    backend = CacheSession

    def test_actual_expiry(self):
        pass
