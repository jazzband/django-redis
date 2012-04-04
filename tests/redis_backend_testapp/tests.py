# -*- coding: utf-8 -*-

from django.test import TestCase
from django.core.cache import cache
import datetime

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

        self.assertIsInstance(res, str)
        self.assertEqual(res, "hello")

    def test_save_unicode(self):
        self.cache.set("test_key", u"heló")
        res = self.cache.get("test_key")

        self.assertIsInstance(res, unicode)
        self.assertEqual(res, u"heló")

    def test_save_dict(self):
        now_dt = datetime.datetime.now()
        test_dict = {'id':1, 'date': now_dt, 'name': u'Foo'}
        
        self.cache.set("test_key", test_dict)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, dict)
        self.assertEqual(res['id'], 1)
        self.assertEqual(res['name'], u'Foo')
        self.assertEqual(res['date'], now_dt)

    def test_save_float(self):
        float_val = 1.345620002

        self.cache.set("test_key", float_val)
        res = self.cache.get("test_key")

        self.assertIsInstance(res, float)
        self.assertEqual(res, float_val)
