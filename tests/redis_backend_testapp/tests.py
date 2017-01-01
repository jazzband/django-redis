# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals, print_function

import base64
import unittest
import sys
import time
import datetime
from datetime import timedelta

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from mock import Mock

from django.conf import settings
from django.core.cache import cache
from django import VERSION
from django.test import TestCase

import fakeredis

import django_redis.cache
from django_redis import pool
from django_redis.client import DefaultClient
from django_redis.client import ShardClient
from django_redis.client import herd

from django_redis.serializers import json as json_serializer
from django_redis.serializers import msgpack as msgpack_serializer


FAKE_REDIS = settings.CACHES["default"]["OPTIONS"].get("REDIS_CLIENT_CLASS") \
             == "fakeredis.FakeStrictRedis"

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
        self.constring4 = "unix://tmp/foo.bar?db=1"
        self.constring5 = "redis://localhost/2"
        self.constring6 = "rediss://localhost:3333?db=2"

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
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), set(["foo-bb", "foo-bc"]))
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
        self.cache.set("test_key", "hello"*1000)
        res = self.cache.get("test_key")

        type(res)
        self.assertIsInstance(res, text_type)
        self.assertEqual(res, "hello"*1000)

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
        if isinstance(self.cache.client._serializer,
                      json_serializer.JSONSerializer):
            self.skipTest("Datetimes are not JSON serializable")

        if isinstance(self.cache.client._serializer,
                      msgpack_serializer.MSGPackSerializer):
            #MSGPackSerializer serializers use the isoformat for datetimes
            #https://github.com/msgpack/msgpack-python/issues/12
            now_dt = datetime.datetime.now().isoformat()
        else:
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
        self.assertEqual(res, None)

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

    def test_delete_many_generator(self):
        self.cache.set_many({"a": 1, "b": 2, "c": 3})
        res = self.cache.delete_many(key for key in ["a","b"])
        self.assertTrue(bool(res))

        res = self.cache.get_many(["a", "b", "c"])
        self.assertEqual(res, {"c": 3})

        res = self.cache.delete_many(["a","b"])
        self.assertFalse(bool(res))

    def test_delete_many_empty_generator(self):
        res = self.cache.delete_many(key for key in [])
        self.assertFalse(bool(res))

    def test_incr(self):
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis doesn't support eval")
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

    def test_incr_error(self):
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis doesn't support eval")
        try:
            with self.assertRaises(ValueError):
                # key not exists
                self.cache.incr('numnum')
        except NotImplementedError:
            raise unittest.SkipTest("`incr` not supported in herd client")


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
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis doesn't support eval")
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
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        res = self.cache.delete_pattern("*foo-a*")
        self.assertTrue(bool(res))

        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), set(["foo-bb", "foo-bc"]))

        res = self.cache.delete_pattern("*foo-a*")
        self.assertFalse(bool(res))

    @patch('django_redis.cache.RedisCache.client')
    def test_delete_pattern_with_custom_count(self, client_mock):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")

        self.cache.delete_pattern("*foo-a*", itersize=2)

        client_mock.delete_pattern.assert_called_once_with("*foo-a*", itersize=2)

    @patch('django_redis.cache.RedisCache.client')
    def test_delete_pattern_with_settings_default_scan_count(self, client_mock):
        for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
            self.cache.set(key, "foo")
        expected_count = django_redis.cache.DJANGO_REDIS_SCAN_ITERSIZE

        self.cache.delete_pattern("*foo-a*")

        client_mock.delete_pattern.assert_called_once_with("*foo-a*", itersize=expected_count)

    def test_close(self):
        cache = caches["default"]
        cache.set("f", "1")
        cache.close()

    def test_ttl(self):
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis ttl is broken, see https://github.com/jamesls/fakeredis/issues/119")

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
        self.assertEqual(ttl, 0)

        # Test ttl with not existent key
        ttl = cache.ttl("not-existent-key")
        self.assertEqual(ttl, 0)

    def test_persist(self):
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis ttl is broken, see https://github.com/jamesls/fakeredis/issues/119")

        self.cache.set("foo", "bar", timeout=20)
        self.cache.persist("foo")

        ttl = self.cache.ttl("foo")
        self.assertIsNone(ttl)

    def test_expire(self):
        self.cache.set("foo", "bar", timeout=None)
        self.cache.expire("foo", 20)
        ttl = self.cache.ttl("foo")
        self.assertAlmostEqual(ttl, 20)

    def test_lock(self):
        if FAKE_REDIS:
            raise unittest.SkipTest("FakeRedis doesn't support locks")
        lock = self.cache.lock("foobar")
        lock.acquire(blocking=True)

        self.assertTrue(self.cache.has_key("foobar"))
        lock.release()
        self.assertFalse(self.cache.has_key("foobar"))

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

    def test_zlib_compressor(self):
        pass


import django_redis.cache


class DjangoOmitExceptionsTests(TestCase):
    def setUp(self):
        self._orig_setting = django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS
        django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
        self.cache = caches["doesnotexist"]
        self.cache._orig_ignore_exceptions = self.cache._ignore_exceptions
        self.cache._ignore_exceptions = True

    def tearDown(self):
        django_redis.cache.DJANGO_REDIS_IGNORE_EXCEPTIONS = self._orig_setting
        self.cache._ignore_exceptions = self.cache._orig_ignore_exceptions

    def test_get_many_returns_default_arg(self):
        self.assertEqual(self.cache.get_many(["key1", "key2", "key3"]), {})

    def test_get(self):
        self.assertIsNone(self.cache.get("key"))
        self.assertEqual(self.cache.get("key", "default"), "default")
        self.assertEqual(self.cache.get("key", default="default"), "default")


from django.contrib.sessions.backends.cache import SessionStore as CacheSession

from django.contrib.sessions.serializers import (
    JSONSerializer, PickleSerializer,
)
from django.core import management
from django.core.cache import caches
from django.test import override_settings
from django.test.utils import patch_logger
from django.utils import six, timezone

class SessionTestsMixin(object):
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
        self.assertFalse(self.session.modified)
        self.assertFalse(self.session.accessed)

    def test_get_empty(self):
        self.assertEqual(self.session.get('cat'), None)

    def test_store(self):
        self.session['cat'] = "dog"
        self.assertTrue(self.session.modified)
        self.assertEqual(self.session.pop('cat'), 'dog')

    def test_pop(self):
        self.session['some key'] = 'exists'
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(self.session.pop('some key'), 'exists')
        self.assertTrue(self.session.accessed)
        self.assertTrue(self.session.modified)
        self.assertEqual(self.session.get('some key'), None)

    def test_pop_default(self):
        self.assertEqual(self.session.pop('some key', 'does not exist'),
                         'does not exist')
        self.assertTrue(self.session.accessed)
        self.assertFalse(self.session.modified)

    def test_setdefault(self):
        self.assertEqual(self.session.setdefault('foo', 'bar'), 'bar')
        self.assertEqual(self.session.setdefault('foo', 'baz'), 'bar')
        self.assertTrue(self.session.accessed)
        self.assertTrue(self.session.modified)

    def test_update(self):
        self.session.update({'update key': 1})
        self.assertTrue(self.session.accessed)
        self.assertTrue(self.session.modified)
        self.assertEqual(self.session.get('update key', None), 1)

    def test_has_key(self):
        self.session['some key'] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn('some key', self.session)
        self.assertTrue(self.session.accessed)
        self.assertFalse(self.session.modified)

    def test_values(self):
        self.assertEqual(list(self.session.values()), [])
        self.assertTrue(self.session.accessed)
        self.session['some key'] = 1
        self.assertEqual(list(self.session.values()), [1])

    def test_iterkeys(self):
        self.session['x'] = 1
        self.session.modified = False
        self.session.accessed = False
        i = six.iterkeys(self.session)
        self.assertTrue(hasattr(i, '__iter__'))
        self.assertTrue(self.session.accessed)
        self.assertFalse(self.session.modified)
        self.assertEqual(list(i), ['x'])

    def test_itervalues(self):
        self.session['x'] = 1
        self.session.modified = False
        self.session.accessed = False
        i = six.itervalues(self.session)
        self.assertTrue(hasattr(i, '__iter__'))
        self.assertTrue(self.session.accessed)
        self.assertFalse(self.session.modified)
        self.assertEqual(list(i), [1])

    def test_iteritems(self):
        self.session['x'] = 1
        self.session.modified = False
        self.session.accessed = False
        i = six.iteritems(self.session)
        self.assertTrue(hasattr(i, '__iter__'))
        self.assertTrue(self.session.accessed)
        self.assertFalse(self.session.modified)
        self.assertEqual(list(i), [('x', 1)])

    def test_clear(self):
        self.session['x'] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [('x', 1)])
        self.session.clear()
        self.assertEqual(list(self.session.items()), [])
        self.assertTrue(self.session.accessed)
        self.assertTrue(self.session.modified)

    def test_save(self):
        if (hasattr(self.session, '_cache') and 'DummyCache' in
                settings.CACHES[settings.SESSION_CACHE_ALIAS]['BACKEND']):
            raise unittest.SkipTest("Session saving tests require a real cache backend")
        self.session.save()
        self.assertTrue(self.session.exists(self.session.session_key))

    def test_delete(self):
        self.session.save()
        self.session.delete(self.session.session_key)
        self.assertFalse(self.session.exists(self.session.session_key))

    def test_flush(self):
        self.session['foo'] = 'bar'
        self.session.save()
        prev_key = self.session.session_key
        self.session.flush()
        self.assertFalse(self.session.exists(prev_key))
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertIsNone(self.session.session_key)
        self.assertTrue(self.session.modified)
        self.assertTrue(self.session.accessed)

    def test_cycle(self):
        self.session['a'], self.session['b'] = 'c', 'd'
        self.session.save()
        prev_key = self.session.session_key
        prev_data = list(self.session.items())
        self.session.cycle_key()
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertEqual(list(self.session.items()), prev_data)

    def test_save_doesnt_clear_data(self):
        self.session['a'] = 'b'
        self.session.save()
        self.assertEqual(self.session['a'], 'b')

    def test_invalid_key(self):
        # Submitting an invalid session key (either by guessing, or if the db has
        # removed the key) results in a new key being generated.
        try:
            session = self.backend('1')
            try:
                session.save()
            except AttributeError:
                self.fail(
                    "The session object did not save properly. "
                    "Middleware may be saving cache items without namespaces."
                )
            self.assertNotEqual(session.session_key, '1')
            self.assertEqual(session.get('cat'), None)
            session.delete()
        finally:
            # Some backends leave a stale cache entry for the invalid
            # session key; make sure that entry is manually deleted
            session.delete('1')

    if VERSION[:2] != (1, 8):
        def test_session_key_empty_string_invalid(self):
            """Falsey values (Such as an empty string) are rejected."""
            self.session._session_key = ''
            self.assertIsNone(self.session.session_key)

        def test_session_key_too_short_invalid(self):
            """Strings shorter than 8 characters are rejected."""
            self.session._session_key = '1234567'
            self.assertIsNone(self.session.session_key)

    def test_session_key_valid_string_saved(self):
        """Strings of length 8 and up are accepted and stored."""
        self.session._session_key = '12345678'
        self.assertEqual(self.session.session_key, '12345678')

    def test_session_key_is_read_only(self):
        def set_session_key(session):
            session.session_key = session._get_new_session_key()
        self.assertRaises(AttributeError, set_session_key, self.session)

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
            self.assertFalse(self.session.get_expire_at_browser_close())

            self.session.set_expiry(0)
            self.assertTrue(self.session.get_expire_at_browser_close())

            self.session.set_expiry(None)
            self.assertFalse(self.session.get_expire_at_browser_close())

        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
            self.session.set_expiry(10)
            self.assertFalse(self.session.get_expire_at_browser_close())

            self.session.set_expiry(0)
            self.assertTrue(self.session.get_expire_at_browser_close())

            self.session.set_expiry(None)
            self.assertTrue(self.session.get_expire_at_browser_close())

    def test_decode(self):
        # Ensure we can decode what we encode
        data = {'a test key': 'a test value'}
        encoded = self.session.encode(data)
        self.assertEqual(self.session.decode(encoded), data)

    def test_decode_failure_logged_to_security(self):
        bad_encode = base64.b64encode(b'flaskdj:alkdjf')
        with patch_logger('django.security.SuspiciousSession', 'warning') as calls:
            self.assertEqual({}, self.session.decode(bad_encode))
            # check that the failed decode is logged
            self.assertEqual(len(calls), 1)
            self.assertIn('corrupted', calls[0])

    def test_actual_expiry(self):
        # this doesn't work with JSONSerializer (serializing timedelta)
        with override_settings(SESSION_SERIALIZER='django.contrib.sessions.serializers.PickleSerializer'):
            self.session = self.backend()  # reinitialize after overriding settings

            # Regression test for #19200
            old_session_key = None
            new_session_key = None
            try:
                self.session['foo'] = 'bar'
                self.session.set_expiry(-timedelta(seconds=10))
                self.session.save()
                old_session_key = self.session.session_key
                # With an expiry date in the past, the session expires instantly.
                new_session = self.backend(self.session.session_key)
                new_session_key = new_session.session_key
                self.assertNotIn('foo', new_session)
            finally:
                self.session.delete(old_session_key)
                self.session.delete(new_session_key)


class SessionTests(SessionTestsMixin, TestCase):
    backend = CacheSession

    def test_actual_expiry(self):
        pass


class TestDefaultClient(TestCase):

    @patch('redis_backend_testapp.tests.DefaultClient.get_client')
    @patch('redis_backend_testapp.tests.DefaultClient.__init__', return_value=None)
    def test_delete_pattern_calls_get_client_given_no_client(self, init_mock, get_client_mock):
        client = DefaultClient()
        client._backend = Mock()

        client.delete_pattern(pattern='foo*')

        get_client_mock.assert_called_once_with(write=True)

    @patch('redis_backend_testapp.tests.DefaultClient.make_key')
    @patch('redis_backend_testapp.tests.DefaultClient.__init__', return_value=None)
    def test_delete_pattern_calls_make_key(self, init_mock, make_key_mock):
        client = DefaultClient()
        client._backend = Mock()
        redis_client = fakeredis.FakeStrictRedis()
        client.delete_pattern(pattern='foo*', client=redis_client)

        make_key_mock.assert_called_once_with('foo*', version=None, prefix=None)

    @patch('redis_backend_testapp.tests.DefaultClient.make_key')
    @patch('redis_backend_testapp.tests.DefaultClient.get_client', return_value=Mock())
    @patch('redis_backend_testapp.tests.DefaultClient.__init__', return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
            self, init_mock, get_client_mock, make_key_mock):
        client = DefaultClient()
        client._backend = Mock()
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern='foo*', itersize=90210)

        get_client_mock.return_value.scan_iter.assert_called_once_with(
            count=90210, match=make_key_mock.return_value)


class TestShardClient(TestCase):

    @patch('redis_backend_testapp.tests.DefaultClient.make_key')
    @patch('redis_backend_testapp.tests.ShardClient.__init__', return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
            self, init_mock, make_key_mock):
        client = ShardClient()
        client._backend = Mock()
        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {'test': connection}

        client.delete_pattern(pattern='foo*', itersize=10)

        connection.scan_iter.assert_called_once_with(count=10, match=make_key_mock.return_value)

    @patch('redis_backend_testapp.tests.DefaultClient.make_key')
    @patch('redis_backend_testapp.tests.ShardClient.__init__', return_value=None)
    def test_delete_pattern_calls_scan_iter(self, init_mock, make_key_mock):
        client = ShardClient()
        client._backend = Mock()
        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {'test': connection}

        client.delete_pattern(pattern='foo*')

        connection.scan_iter.assert_called_once_with(match=make_key_mock.return_value)

    @patch('redis_backend_testapp.tests.DefaultClient.make_key')
    @patch('redis_backend_testapp.tests.ShardClient.__init__', return_value=None)
    def test_delete_pattern_calls_delete_for_given_keys(self, init_mock, make_key_mock):
        client = ShardClient()
        client._backend = Mock()
        connection = Mock()
        connection.scan_iter.return_value = [Mock(), Mock()]
        connection.delete.return_value = 0
        client._serverdict = {'test': connection}

        client.delete_pattern(pattern='foo*')

        connection.delete.assert_called_once_with(*connection.scan_iter.return_value)
