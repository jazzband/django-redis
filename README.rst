==========================
Redis Django Cache Backend
==========================

A simple Redis cache backend for Django

Redis cache allows you to use either a TCP connection or Unix domain
socket to connect to your redis server.  Using a TCP connection is useful for
when you have your redis server separate from your app server and/or within
a distributed environment.  Unix domain sockets are useful if you have your
redis server and application running on the same machine and want the fastest
possible connection.

You can specify (optionally) what parser class you want redis-py to use
when parsing messages from the redis server.  redis-py will pick the best
parser for you implicitly, but using the ``PARSER_CLASS`` setting gives you
control and the option to roll your own parser class if you are so bold.

Notes
-----

This cache backend requires the `redis-py`_ Python client library for
communicating with the Redis server.

Redis writes to disk asynchronously so there is a slight chance
of losing some data, but for most purposes this is acceptable.

This cache backend is full ready for `django-orm`_ cache.


How to install.
---------------

Run ``python setup.py install`` to install, 
or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Usage cache backend.
--------------------

Modify your Django settings to use ``redis_cache`` ::

    # When using TCP connections
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
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
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': '/path/to/socket/file',
            'OPTIONS': {
                'DB': 1,
                'PASSWORD': 'yadayada', 
                'PICKLE_VERSION': -1,   # default
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            },
        },
    }


Usage redis_cache.stats django-app.
-----------------------------------

1. Place ``redis_cache.stats`` on your INSTALLED_APPS.

2. Add this url on your urls.py::
    
    url(r'^redis/status/', include('redis_cache.stats.urls', namespace='redis_cache'))


Note: only tested with django >= 1.3


TODO:
-----

* Improve stats django-app: add more administration options.
* Add garbage collection and memory limits options.

.. _redis-py: http://github.com/andymccurdy/redis-py/
