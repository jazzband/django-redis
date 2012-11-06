# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.test import TestCase
from django.core.cache import cache, get_cache
import time
import datetime

import sys
if sys.version_info.major < 3:
    text_type = unicode
    bytes_type = str
else:
    text_type = str
    bytes_type = bytes


class DjangoRedisCacheTests(TestCase):
    def setUp(self):
        self.cache = cache

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

    def test_decr(self):
        self.cache.set("num", 20)

        self.cache.decr("num")
        res = self.cache.get("num")
        self.assertEqual(res, 19)

        self.cache.decr("num", 20)
        res = self.cache.get("num")
        self.assertEqual(res, -1)

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
