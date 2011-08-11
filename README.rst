==========================
Redis Django Cache Backend
==========================

A simple Redis cache backend for Django

Notes
-----

This cache backend requires the `redis-py`_ Python client library for communicating with the Redis server.

Redis writes to disk asynchronously so there is a slight chance 
of losing some data, but for most purposes this is acceptable.

This version is not the same that is in PyPI

Usage cache backend.
--------------------

1. Run ``python setup.py install`` to install, 
   or place ``redis_cache`` on your Python path.

2. Modify your Django settings to use ``redis_cache`` :

On Django < 1.3::

    CACHE_BACKEND = 'redis_cache.cache://<host>:<port>'

On Django >= 1.3::

    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.RedisCache',
            'LOCATION': '<host>:<port>',
            'OPTIONS': { # optional
                'DB': 1,
                'PASSWORD': 'yadayada', 
                'PICKLE_VERSION': -1,   # default
            },
        },
    }


Usage redis_cache.status djago-app.
-----------------------------------

1. Place 'redis_cache.stats' on your INSTALLED_APPS.
2. Add this url on your urls.py:
    url(r'^redis/status/', include('redis_cache.stats.urls', namespace='redis_cache'))


Note: only tested with django >= 1.3

.. _redis-py: http://github.com/andymccurdy/redis-py/
