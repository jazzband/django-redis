==========================
Redis Django Cache Backend
==========================

A simple Redis cache backend for Django.

Notes
-----

The Python wrapper required by this library is distributed with Redis,
and can be found in your local installation at ::

    [redis dir]/client-libraries/python/redis.py
    
or at `Redis's GitHub Repo`_.

Redis writes to disk asynchronously so there is a slight chance 
of losing some data, but for most purposes this is acceptable.

Usage
-----

1. Run ``python setup.py install`` to install, 
   or place ``redis_cache`` on your Python path.
2. Modify your Django settings to use ``redis_cache`` ::

    CACHE_BACKEND = 'redis_cache.cache://<host>:<port>'



.. _Redis's Github Repo: http://github.com/antirez/redis/tree/master/client-libraries/python/