# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import smart_text, python_2_unicode_compatible


@python_2_unicode_compatible
class CacheKey(str):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def __init__(self, key):
        self._key = key

    def __str__(self):
        return smart_text(self._key)

    def original_key(self):
        key = self._key.rsplit(":", 1)[1]
        return key


def load_class(path):
    """
    Loads class from path.
    """

    mod_name, klass_name = path.rsplit('.', 1)

    try:
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImproperlyConfigured('Error importing {0}: "{1}"'.format(mod_name, e))

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "{0}" does not define a "{1}" class'.format(mod_name, klass_name))

    return klass


def default_reverse_key(key):
    return key.split(':', 2)[2]
