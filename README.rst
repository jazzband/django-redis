==============================
Redis cache backend for Django
==============================

Full featured redis cache backend for Django.

**NOTE**: The 3.0 version has many changes in the code, and may have regressiones. If you want a version more stable and proven, use the 2.x branch


Generic description
-------------------

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


Features:
---------

* In active development.
* Sharding supported in a single package.
* Complete battery of tests (accepting improvements).
* Used in production environments on several projects.
* Can set keys with infinite timeout: ``cache.set('key', 'value', timeout=0)``
* Pluggable clients.
* Python3 support with same codebase.
* Same behavior as memcached backend with connection exceptions.
* Supports Django: 1.3, 1.4 and 1.5
* You can take advantage of the connection pool to directly access to the connection object of redis.


Future plans/In developement
----------------------------

* Auto failover
* Master-Slave pluggable client.


Coming from ``django-redis-cache``
----------------------------------

Currently, for django versions ``>1.3``, migration is very easy, since there is no significant difference in connection APIs.
The only point is the connection string that since version 3.0 has changed slightly. You can look at the differences in the later sections.


How to install
--------------

Run ``python setup.py install`` to install,
or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Usage of cache backend
----------------------

To start using ``django-redis``, you must change your django cache settings. ``django-redis`` implements the standard interface for django cache backends.

With ``django-redis==3.0`` has introduced certain backwards incompatible changes, in part of redis connection settings (connection string). 
The ``LOCATION`` attr string must be have always three colons instead of two.

Old way (django-redis < 3.0):

.. code-block:: python

    CACHES = {
        "default": {
            #...
            "LOCATION": "ip:port",
            "OPTIONS": {
                "DB": 1
            }
        }
    }

New way:

.. code-block:: python

    CACHES = {
        "default": {
            #...
            "LOCATION": "ip:port:db",
        }
    }


This is the complete example using a tcp connection:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "redis_cache.cache.RedisCache",
            "LOCATION": "127.0.0.1:6379:1",
            "OPTIONS": {
                "CLIENT_CLASS": "redis_cache.client.DefaultClient",
            }
        }
    }


And this is a complete example using unix sockets:

.. code-block:: python

    # When using unix domain sockets
    # Note: ``LOCATION`` needs to be the same as the ``unixsocket`` setting
    # in your redis.conf
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': 'unix:/path/to/socket/file.sock:1',
            'OPTIONS': {
                'PASSWORD': 'foopassword',
                'PICKLE_VERSION': -1,   # default
                'PARSER_CLASS': 'redis.connection.HiredisParser'
                'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
            },
        },
    }


Optionally, with ``PARSER_CLASS="redis.connection.HiredisParser"`` you can set hiredis parser.


How to use client-side sharding pluggable client?
-------------------------------------------------

The configuration is same as a default with unique diference: the ``LOCATION`` attr must
be a list of connection strings.


Some example:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "redis_cache.cache.RedisCache",
            "LOCATION": [
                "127.0.0.1:6379:1",
                "127.0.0.1:6379:2",
            ],
            "OPTIONS": {
                "CLIENT_CLASS": "redis_cache.client.ShardClient",
            }
        }
    }


Extra methods added by ``django-redis``
---------------------------------------

``django-redis`` provides 2 additional methods to the standard django-cache api interface:

* ``cache.keys(wildcard_pattern)`` - Add abilite to retrieve a list of keys with wildcard pattern.
* ``cache.delete_pattern(wildcard_pattern)`` - Same as ``keys``, but this delete all keys matching the wildcard pattern.


Example:

.. code-block:: python

    from django.core.cache import cache
    # this returns all keys starts with ``session_``
    result = cache.keys("session_*")

    # delete all keys stats with ``session_``
    cache.delete_pattern("session_*")


Access to raw redis connection
------------------------------

And sometimes, our application requires direct access to redis, besides the standard cache.

Instead of repeating the code 2 times and create multiple connection pool, ``django-redis`` exposes a simple API to access
the redis client directly, bypassing the cache API. This allows an application that needs the cache API and direct access to redis,
have everything in one.

Example:

.. code-block:: python

    >>> from redis_cache import get_redis_connection
    >>> con = get_redis_connection('default')
    >>> con
    <redis.client.Redis object at 0x2dc4510>


**NOTE**: not all pluggable clients supports this feature. The simple example is a ShardClient, this does not supports
access to raw redis connection.

.. _redis-py: http://github.com/andymccurdy/redis-py/
