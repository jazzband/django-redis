# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

# Import the fastest implementation of
# pickle package. This should be removed
# when python3 come the unique supported
# python version
try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.core.exceptions import ImproperlyConfigured

try:
    from django.utils.encoding import force_bytes
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import smart_bytes as force_bytes
    from django.utils.encoding import force_unicode as force_text


from .base import BaseSerializer


class PickleSerializer(BaseSerializer):
    def __init__(self, options):
        self._pickle_version = -1
        self.setup_pickle_version(options)

    def setup_pickle_version(self, options):
        if "PICKLE_VERSION" in options:
            try:
                self._pickle_version = int(options["PICKLE_VERSION"])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def dumps(self, value):
        return pickle.dumps(value, self._pickle_version)

    def loads(self, value):
        return pickle.loads(force_bytes(value))
