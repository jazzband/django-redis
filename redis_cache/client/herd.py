# -*- coding: utf-8 -*-

import time

from django.conf import settings
from django.utils.datastructures import SortedDict

from . import default


class Marker(object):
    """
    Dummy class for use as
    marker for herded keys.
    """
    pass


CACHE_HERD_TIMEOUT = getattr(settings, 'CACHE_HERD_TIMEOUT', 60)


class HerdClient(default.DefaultClient):
    def __init__(self, *args, **kwargs):
        self._marker = Marker()
        super(HerdClient, self).__init__(*args, **kwargs)

    def _pack(self, value, timeout):
        herd_timeout = (timeout or self.default_timeout) + int(time.time())
        return (self._marker, value, herd_timeout)

    def _unpack(self, value):
        try:
            marker, unpacked, herd_timeout = value
        except (ValueError, TypeError):
            return value, False

        if not isinstance(marker, Marker):
            return value, False

        if herd_timeout < int(time.time()):
            return unpacked, True

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
            super(HerdClient, self).set(key, val, CACHE_HERD_TIMEOUT)
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

        reinsert = {}

        for key, value in zip(new_keys, results):
            if value is None:
                continue

            val, refresh = self._unpack(self.unpickle(value))
            if refresh:
                recovered_data[map_keys[key]] = None
                reinsert[map_keys[key]] = val
            else:
                recovered_data[map_keys[key]] = val

        if reinsert:
            self.set_many(reinsert, CACHE_HERD_TIMEOUT)

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
