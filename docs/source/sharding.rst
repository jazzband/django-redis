Client side sharding
--------------------

.. versionadded:: 2.1

A database shard is a horizontal partition in a database or search engine. Each individual partition is referred to as a shard or database shard. ``django-redis`` implements a hashring client side sharding for redis. The initial implementation is released on ``django-redis`` version 2.1 but with new changes introduces in version 3.0 makes some old configuration backward incompatible.


On old way, the shard backend was distinct of the standart backend. Now, with django-redis 3.0, available only a single backend and for use sharding, simply specify ``CLIENT_CLASS`` attribute on ``CACHE['OPTIONS']`` with a location of sharded client: ``redis_cache.client.ShardClient``

This is a simple and complete example:

.. code-block:: python

    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': [
                '127.0.0.1:6379:1',
                '127.0.0.1:6379:2',
            ],
            'OPTIONS': {
                'CLIENT_CLASS': 'redis_cache.client.ShardClient',
            }
        }
    }

