.. django-redis documentation master file, created by
   sphinx-quickstart on Sat Feb  2 20:14:51 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

django-redis
============

Release v\ |version|.

django-redis is a :ref:`BSD Licensed`, full featured redis cache backend for Django.


Features:
---------

* In active development.
* Sharding supported in a single package.
* Complete battery of tests (accepting improvements).
* Used in production environments on several projects.
* Can set keys with infinite timeout: ``cache.set('key', 'value', timeout=0)``
* Pluggable clients.
* Python3 support with same codebase.
* Supports Django: 1.3, 1.4 and 1.5
* Can take advantage of the connection pool with directly access to the raw redis connection.
* Can emulate memcached backend behavior with connection exceptions (see more :ref:`Settings <settings>`)

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


Coming from ``django-redis-cache``
----------------------------------

Currently, for django versions ``>1.3``, migration is very easy, since there is no
significant difference in connection APIs. The only point is the connection string that
since version 3.0 has changed slightly. You can look at the differences in the later sections.


How to install
--------------

Run ``python setup.py install`` to install,
or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Usage of cache backend
----------------------

To start using django-redis, you must change your django cache settings. django-redis implements the standard interface for django cache backends.

With django-redis v3.x has introduced certain backwards incompatible changes, in part of redis connection settings (connection string).
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
                'PARSER_CLASS': 'redis.connection.HiredisParser',
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

django-redis provides 2 additional methods to the standard django-cache api interface:

* ``cache.keys(wildcard_pattern)`` - Add abilite to retrieve a list of keys with wildcard pattern.
* ``cache.delete_pattern(wildcard_pattern)`` - Same as ``keys``, but this delete all keys matching the wildcard pattern.


Example:

.. code-block:: python

    from django.core.cache import cache
    # this returns all keys starts with ``session_``
    result = cache.keys("session_*")

    # delete all keys stats with ``session_``
    cache.delete_pattern("session_*")


.. versionadded:: 3.1.6

django-redis also provides an additional parameter to set method: **nx**. If set to ``True`` django-redis will use
setnx instead of set. **timeout** is still suported and setting it will result in a call to expire if the key was set.


Example:

.. code-block:: python

    >>> from django.core.cache import cache
    >>> cache.set("key", "value1", nx=True)
    True
    >>> cache.set("key", "value2", nx=True)
    False
    >>> cache.get("key")
    "value1"


.. _settings:

Extra settings added by django-redis
------------------------------------

.. versionadded:: 3.0

After version 3.0, changed behavior related to connection failure exceptions. Now, the behavior is identical to memcached.
If redis is offline, the operations with cache do not throw exception and just return None.

To return to the previous behavior (if redis is offline, the cache operations throw an exception),
put ``DJANGO_REDIS_IGNORE_EXCEPTIONS`` setting value to False.

.. versionchanged:: 3.2

Now, on 3.2 version, the initial behavior is reverted, and if you would memcached behavior, you need set
``DJANGO_REDIS_IGNORE_EXCEPTIONS`` to True (now, by default is False)


Specifying a timeout for Redis operations
-----------------------------------------

You can optionally set a timeout for redis operations by specifying an integer or float value for
``SOCKET_TIMEOUT`` in your ``CACHES`` entry:

.. code-block:: python

    CACHES = {
        'default': {
            ...
            'OPTIONS': {
                'SOCKET_TIMEOUT': 5,
            },
        },
    }

If set, redis will time out after ``SOCKET_TIMEOUT`` seconds. This can occur for multiple reasons, such as
redis being down or unavailable, or Redis not returning quickly enough if your timeout is set too low.

If you have ``DJANGO_REDIS_IGNORE_EXCEPTIONS`` set to ``True``, timeouts will silently return ``None``.
Otherwise, an exception will be raised.


Access to raw redis connection
------------------------------

.. versionadded:: 3.1

And sometimes, our application requires direct access to redis, besides the standard cache.

Instead of repeating the code 2 times and create multiple connection pool, django-redis exposes a simple API to access
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
