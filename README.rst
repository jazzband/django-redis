==========================
Redis Django Cache Backend
==========================

A simple Redis cache backend for Django

Changes in 0.9.0
================

Redis cache now allows you to use either a TCP connection or Unix domain
socket to connect to your redis server.  Using a TCP connection is useful for
when you have your redis server separate from your app server and/or within
a distributed environment.  Unix domain sockets are useful if you have your
redis server and application running on the same machine and want the fastest
possible connection.

You can now specify (optionally) what parser class you want redis-py to use
when parsing messages from the redis server.  redis-py will pick the best
parser for you implicitly, but using the ``PARSER_CLASS`` setting gives you
control and the option to roll your own parser class if you are so bold.

Notes
-----

This cache backend requires the `redis-py`_ Python client library for
communicating with the Redis server.

Redis writes to disk asynchronously so there is a slight chance
of losing some data, but for most purposes this is acceptable.

Usage
-----

1. Run ``python setup.py install`` to install,
   or place ``redis_cache`` on your Python path.

2. Modify your Django settings to use ``redis_cache`` :

On Django < 1.3::

    CACHE_BACKEND = 'redis_cache.cache://<host>:<port>'

On Django >= 1.3::


    # When using TCP connections
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.RedisCache',
            'LOCATION': '<host>:<port>',
            'OPTIONS': {
                'DB': 1,
                'PASSWORD': 'yadayada',
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            },
        },
    }

    # When using unix domain sockets
    # Note: ``LOCATION`` needs to be the same as the ``unixsocket`` setting
    # in your redis.conf
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.RedisCache',
            'LOCATION': '/path/to/socket/file',
            'OPTIONS': {
                'DB': 1,
                'PASSWORD': 'yadayada',
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            },
        },
    }

.. _redis-py: http://github.com/andymccurdy/redis-py/
