# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.test import TestCase
from django.core.cache import cache, get_cache
import time
import datetime

import sys
if sys.version_info[0] < 3:
    text_type = unicode
    bytes_type = str
else:
    text_type = str
    bytes_type = bytes
    long = int

class DjangoRedisCacheTests(TestCase):
    def setUp(self):
        self.cache = cache

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
        res = self.cache.set("test_key_nx", 1, timeout=2, nx=True)
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
        test_dict = {'id':1, 'date': now_dt, 'name': 'Foo'}

        self.cache.set("test_key", test_dict)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, dict)
        self.assertEqual(res['id'], 1)
        self.assertEqual(res['name'], 'Foo')
        self.assertEqual(res['date'], now_dt)

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

    def test_set_add(self):
        self.cache.set('add_key', 'Initial value')
        self.cache.add('add_key', 'New value')
        res = cache.get('add_key')

        self.assertEqual(res, 'Initial value')

    def test_get_many(self):
        self.cache.set('a', 1)
        self.cache.set('b', 2)
        self.cache.set('c', 3)

        res = self.cache.get_many(['a','b','c'])
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3})

    def test_get_many_unicode(self):
        self.cache.set('a', '1')
        self.cache.set('b', '2')
        self.cache.set('c', '3')

        res = self.cache.get_many(['a','b','c'])
        self.assertEqual(res, {'a': '1', 'b': '2', 'c': '3'})

    def test_set_many(self):
        self.cache.set_many({'a': 1, 'b': 2, 'c': 3})
        res = self.cache.get_many(['a', 'b', 'c'])
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3})

    def test_delete(self):
        self.cache.set_many({'a': 1, 'b': 2, 'c': 3})
        self.cache.delete('a')

        res = self.cache.get_many(['a', 'b', 'c'])
        self.assertEqual(res, {'b': 2, 'c': 3})

    def test_delete_many(self):
        self.cache.set_many({'a': 1, 'b': 2, 'c': 3})
        self.cache.delete_many(['a','b'])
        res = self.cache.get_many(['a', 'b', 'c'])
        self.assertEqual(res, {'c': 3})

    def test_incr(self):
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

    def test_decr(self):
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

    def test_version(self):
        self.cache.set("keytest", 2, version=2)
        res = self.cache.get("keytest")
        self.assertEqual(res, None)

        res = self.cache.get("keytest", version=2)
        self.assertEqual(res, 2)

    def test_incr_version(self):
        self.cache.set("keytest", 2)
        self.cache.incr_version("keytest")

        res = self.cache.get("keytest")
        self.assertEqual(res, None)

        res = self.cache.get("keytest", version=2)
        self.assertEqual(res, 2)

    def test_delete_pattern(self):
        for key in ['foo-aa','foo-ab', 'foo-bb','foo-bc']:
            self.cache.set(key, "foo")

        self.cache.delete_pattern('*foo-a*')
        keys = self.cache.keys("foo*")
        self.assertEqual(set(keys), set(['foo-bb','foo-bc']))

    def test_close(self):
        cache = get_cache('default')
        cache.set("f", "1")
        cache.close()

    def test_reuse_connection_pool(self):
        try:
            cache1 = get_cache('default')
            cache2 = get_cache('default')

            self.assertNotEqual(cache1, cache2)
            self.assertNotEqual(cache1.raw_client, cache2.raw_client)
            self.assertEqual(cache1.raw_client.connection_pool,
                                cache2.raw_client.connection_pool)
        except NotImplementedError:
            pass
