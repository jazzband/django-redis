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

import json

#Use msgpack from http://msgpack.org/
import msgpack

try:
    from django.utils.encoding import smart_bytes
except ImportError:
    from django.utils.encoding import smart_str as smart_bytes

from django.core.exceptions import ImproperlyConfigured


class BaseSerializer(object):
    def __init__(self, options):
        pass

    def dumps(self, value):
        raise NotImplementedError

    def loads(self, value):
        raise NotImplementedError


class PickleSerializer(BaseSerializer):
    def __init__(self, options):
        self._pickle_version = -1
        self.setup_pickle_version(options)

    def setup_pickle_version(self, options):
        if "PICKLE_VERSION" in options:
            try:
                self._pickle_version = int(self._options["PICKLE_VERSION"])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def dumps(self, value):
        return pickle.dumps(value, self._pickle_version)

    def loads(self, value):
        return pickle.loads(smart_bytes(value))


class JSONSerializer(BaseSerializer):
    def dumps(self, value):
        return json.dumps(value)

    def loads(self, value):
        return json.loads(value)


class MSGPackSerializer(BaseSerializer):
    def dumps(self, value):
        return msgpack.dumps(value)

    def loads(self, value):
        return msgpack.loads(value, encoding='utf-8)
