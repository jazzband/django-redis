# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals
import sys

try:
    from django.utils.encoding import smart_text
except ImportError:
    from django.utils.encoding import smart_unicode as smart_text

try:
    from django.utils.encoding import smart_bytes
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from redis import ConnectionPool as RedisConnectionPool
from redis.connection import UnixDomainSocketConnection, Connection
from redis.connection import DefaultParser

from collections import defaultdict
from django.utils.importlib import import_module

if sys.version_info[0] < 3:
    integer_types = (int, long,)
else:
    integer_types = (int,)


class CacheKey(object):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def __init__(self, key):
        self._key = key

    if sys.version_info[0] < 3:
        def __str__(self):
            return smart_bytes(self._key)

        def __unicode__(self):
            return smart_text(self._key)

    else:
        def __str__(self):
            return smart_text(self._key)

    def original_key(self):
        _, key = self._key.rsplit(":", 1)
        return key


class Singleton(type):
    """ Singleton metaclass. """

    def __init__(cls, name, bases, dct):
        cls.__instance = None
        type.__init__(cls, name, bases, dct)

    def __call__(cls, *args, **kw):
        if cls.__instance is None:
            cls.__instance = type.__call__(cls, *args,**kw)
        return cls.__instance


def load_class(path):
    """
    Load class from path.
    """

    try:
        mod_name, klass_name = path.rsplit('.', 1)
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImproperlyConfigured('Error importing {0}: "{1}"'.format(mod_name, e))

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "{0}" does not define a "{1}" class'.format(mod_name, klass_name))

    return klass


