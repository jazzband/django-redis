==========================
Redis Django Cache Backend
==========================

A simple Redis cache backend for Django.

Notes
-----

This cache backend requires the `redis-py`_ Python client library for communicating with the Redis server.

Redis writes to disk asynchronously so there is a slight chance 
of losing some data, but for most purposes this is acceptable.

Usage
-----

1. Run ``python setup.py install`` to install, 
   or place ``redis_cache`` on your Python path.

2. Modify your Django settings to use ``redis_cache`` ::

    CACHE_BACKEND = 'redis_cache.cache://<host>:<port>'



.. _redis-py: http://github.com/andymccurdy/redis-py/

