==============================
Redis cache backend for Django
==============================

It is a fork of ``django-redis-cache``. And the reasons are: The author seems to have abandoned the project and has significant bugs that have not been fixed.


Features:
---------

* In active development.
* Sharding supported in a single package.
* Complete battery of tests (accepting improvements).
* Used in production environments on several projects.

Description.
------------

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

This cache backend requires the `redis-py`_ python client library for
communicating with the Redis server.

This cache backend is full ready for `django-orm-extensions`_ orm cache.


Coming from ``django-redis-cache``.
-----------------------------------

Currently, for django versions ``>1.3``, migration is very easy, since there is no difference in connection APIs. 
The main difference is that ``django-redis`` does not support django versions lower than ``1.3``.


How to install.
---------------

Run ``python setup.py install`` to install, 
or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Changes on 2.0 (2012-04-17)
---------------------------

Now implemented sharding feature. For use it, see this example config::

    CACHES = { 
        'default': {
            'BACKEND': 'redis_cache.cache.ShardedRedisCache',
            'LOCATION': [
                '127.0.0.1:6379:1',
                '127.0.0.1:6379:2',
                'unix:/path/to/socket:3',
            ],  
            'OPTIONS': {
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            }   
        }   
    }

The syntax of a ``LOCATION`` array item is a ``<ip>:<port>:<db>`` or ``unix:<path>:db``.
This feature is stil experimental. Welcome, improvements and bug fixes.


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
                'PASSWORD': 'foopassword', 
                'PICKLE_VERSION': -1,   # default
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            },
        },
    }


Exta methods add by ``django-redis`` to a standar django cache api: ``cache.keys(term)``. This uses
a redis ``keys`` command to find a specific key or collection of keys with glob patterns.

Example:

.. code-block:: python

    from django.core.cache import cache

    # this returns all keys starts with ``session_``
    result = cache.keys("session_*")


Usage redis_cache.stats django-app.
-----------------------------------

1. Place ``redis_cache.stats`` on your INSTALLED_APPS.

2. Add this url on your urls.py::
    
    url(r'^redis/status/', include('redis_cache.stats.urls', namespace='redis_cache'))


Note: only tested with django >= 1.4, if you find a bug that happens with previous versions, I will gladly fix it.

.. _redis-py: http://github.com/andymccurdy/redis-py/
.. _django-orm-extensions: https://github.com/niwibe/django-orm-extensions
