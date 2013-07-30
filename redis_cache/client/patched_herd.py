# -*- coding: utf-8 -*-

import time
from redis.exceptions import ConnectionError
from ..exceptions import ConnectionInterrupted
import random
import os
from django.conf import settings
from django.utils.datastructures import SortedDict
from django.utils.http import parse_http_date_safe

from . import default


class Marker(object):
    """
    Dummy class for use as
    marker for herded keys.
    """
    pass


CACHE_HERD_TIMEOUT = getattr(settings, 'CACHE_HERD_TIMEOUT', 60)


def _is_expired(x):
    if x >= CACHE_HERD_TIMEOUT:
        return True
    val = x + random.randint(1, CACHE_HERD_TIMEOUT)

    if val >= CACHE_HERD_TIMEOUT:
        return True
    else:
        return False


class HerdClient(default.DefaultClient):
    def __init__(self, *args, **kwargs):
        self._marker = Marker()
        super(HerdClient, self).__init__(*args, **kwargs)

    def _pack(self, value, timeout):
        herd_timeout = (timeout or self.default_timeout) + int(time.time())
        last_modified = parse_http_date_safe(value._headers.get('Last-Modified'))

        return (self._marker, value, herd_timeout, last_modified)

    def _unpack(self, value):
        try:
            marker, unpacked, herd_timeout, last_mod = value
        except (ValueError, TypeError):
            return value, False

        if not isinstance(marker, Marker):
            return value, False

        if os.environ.get('GLOBAL_CACHE_TIME', last_mod) > last_mod:
            x = int(time.time()) - os.environ.get('GLOBAL_CACHE_TIME', last_mod)
            return unpacked, _is_expired(x)

        if herd_timeout < int(time.time()):
            x = int(time.time()) - herd_timeout
            return unpacked, _is_expired(x)

        return unpacked, False

    def set(self, key, value, timeout=None, version=None,
            client=None, nx=False):

        if timeout == 0:
            return super(HerdClient, self).set(key, value, timeout=timeout,
                                               version=version, client=client,
                                               nx=nx)
        if timeout is None:
            timeout = self._backend.default_timeout

        packed = self._pack(value, timeout)
        real_timeout = (timeout + CACHE_HERD_TIMEOUT)

        return super(HerdClient, self).set(key, packed, timeout=real_timeout,
                                           version=version, client=client,
                                           nx=nx)

    def get(self, key, default=None, version=None, client=None):
        packed = super(HerdClient, self).get(key, default=default,
                                            version=version, client=client)
        val, refresh = self._unpack(packed)

        if refresh:
            return default

        return val

    def get_many(self, keys, version=None, client=None):
        if client is None:
            client = self.get_client(write=False)

        if not keys:
            return {}

        recovered_data = SortedDict()

        new_keys = list(map(lambda key: self.make_key(key, version=version), keys))
        map_keys = dict(zip(new_keys, keys))

        try:
            results = client.mget(*new_keys)
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

        #reinsert = {}

        for key, value in zip(new_keys, results):
            if value is None:
                continue

            val, refresh = self._unpack(self.unpickle(value))
            if refresh:
                recovered_data[map_keys[key]] = None
                #reinsert[map_keys[key]] = val
            else:
                recovered_data[map_keys[key]] = val

        #if reinsert:
            #self.set_many(reinsert, CACHE_HERD_TIMEOUT)

        return recovered_data

    def set_many(self, data, timeout=None, version=None, client=None,
                 herd=True):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs. This is much more efficient than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        if client is None:
            client = self.get_client(write=True)

        if herd:
            set_function = self.set
        else:
            set_function = super(HerdClient, self).set

        try:
            pipeline = client.pipeline()
            for key, value in data.items():
                set_function(key, value, timeout, version=version, client=pipeline)
            pipeline.execute()
        except ConnectionError:
            raise ConnectionInterrupted(connection=client)

    def incr(self, *args, **kwargs):
        raise NotImplementedError()

    def decr(self, *args, **kwargs):
        raise NotImplementedError()
