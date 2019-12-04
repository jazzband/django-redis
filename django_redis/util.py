# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

try:
    from django.utils.six import text_type
except ImportError:
    text_type = str


class CacheKey(text_type):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def original_key(self):
        return self.rsplit(":", 1)[1]


def default_reverse_key(key):
    return key.split(':', 2)[2]
