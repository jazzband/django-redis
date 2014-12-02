from django.core.cache.backends.dummy import DummyCache


class RedisDummyCache(DummyCache):
    def __init__(self, *args, **kwargs):
        DummyCache.__init__(self, *args, **kwargs)

    @property
    def client(self, *args, **kwargs):
        return self

    def get_client(self, key):
        return self

    def keys(self, *args, **kwargs):
        return []
