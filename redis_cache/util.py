# -*- coding: utf-8 -*-

from django.utils.encoding import smart_unicode, smart_str
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from redis import ConnectionPool as RedisConnectionPool
from redis.connection import UnixDomainSocketConnection, Connection
from redis.connection import DefaultParser

from collections import defaultdict
from importlib import import_module


class CacheKey(object):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def __init__(self, key):
        self._key = key

    def __eq__(self, other):
        return self._key == other

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return self.__unicode__()

    def __unicode__(self):
        return smart_str(self._key)

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
        raise ImproperlyConfigured(u'Error importing %s: "%s"' % (mod_name, e))

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" class' % (mod_name, klass_name))

    return klass


