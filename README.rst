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
* Can set keys with infinite timeout: ``cache.set('key', 'value', timeout=0)``

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

Changelog
---------

* 1.0 First version (fork from django-redis-cache) with ability to select pickle protocol version.
* 1.1 Add stats application for view a server stats.
* 1.2 Add keys method (non standard)
* 1.3 Breaks compatibility with django < 1.3
* 1.4 Now correct handling multiple connection pools.
* 1.5 Bug fixes related with autentication and stats app.
* 2.0 Refactor and initial implementation of client sharding. (testcase rewrite)
* 2.1 Public release with client sharding.
* 2.2 Add delete_pattern method. Useful for delete keys using wildcard syntax.


Coming from ``django-redis-cache``
----------------------------------

Currently, for django versions ``>1.3``, migration is very easy, since there is no difference in connection APIs.
The main difference is that ``django-redis`` does not support django versions lower than ``1.3``.


How to install
--------------

Run ``python setup.py install`` to install,
or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Client side sharding (available since 2.1)
------------------------------------------

Since version 2.1, is available client sharding. For use it, see this example config::

    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.ShardedRedisCache',
            'LOCATION': [
                '127.0.0.1:6379:1',
                '127.0.0.1:6379:2',
                'unix:/path/to/socket:3',
            ],
            # The OPTIONS parameter is optional
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


Optionally, with ``PARSER_CLASS="redis.connection.HiredisParser"`` you can set hiredis parser.


Extra methods added by ``django-redis``
---------------------------------------

``django-redis`` provides 2 additional methods to the standard django-cache api interface:

* ``cache.keys(wildcard_pattern)`` - Add abilite to retrieve a list of keys with wildcard pattern.
* ``cache.delete_pattern`` - Same as ``keys``, but this delete all keys matching the wildcard pattern.


Example::

    from django.core.cache import cache
    # this returns all keys starts with ``session_``
    result = cache.keys("session_*")

    # delete all keys stats with ``session_``
    cache.delete_pattern("session_*")


Usage redis_cache.stats django-app.
-----------------------------------

1. Place ``redis_cache.stats`` on your INSTALLED_APPS.

2. Add this url on your urls.py::

    url(r'^redis/status/', include('redis_cache.stats.urls', namespace='redis_cache'))


Note: only tested with django >= 1.4, if you find a bug that happens with previous versions, I will gladly fix it.

.. _redis-py: http://github.com/andymccurdy/redis-py/
.. _django-orm-extensions: https://github.com/niwibe/django-orm-extensions
