==============================
Redis cache backend for Django
==============================

.. image:: https://jazzband.co/static/img/badge.svg
    :target: https://jazzband.co/
    :alt: Jazzband

.. image:: https://github.com/jazzband/django-redis/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/jazzband/django-redis/actions/workflows/ci.yml
   :alt: GitHub Actions

.. image:: https://codecov.io/gh/jazzband/django-redis/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/jazzband/django-redis
   :alt: Coverage

.. image:: https://img.shields.io/pypi/v/django-redis.svg?style=flat
    :target: https://pypi.org/project/django-redis/

This is a `Jazzband <https://jazzband.co>`_ project. By contributing you agree
to abide by the `Contributor Code of Conduct
<https://jazzband.co/about/conduct>`_ and follow the `guidelines
<https://jazzband.co/about/guidelines>`_.

Introduction
------------

django-redis is a BSD licensed, full featured Redis cache and session backend
for Django.

Why use django-redis?
~~~~~~~~~~~~~~~~~~~~~

- Uses native redis-py url notation connection strings
- Pluggable clients
- Pluggable parsers
- Pluggable serializers
- Primary/secondary support in the default client
- Comprehensive test suite
- Used in production in several projects as cache and session storage
- Supports infinite timeouts
- Facilities for raw access to Redis client/connection pool
- Highly configurable (can emulate memcached exception behavior, for example)
- Unix sockets supported by default

Requirements
~~~~~~~~~~~~

- `Python`_ 3.6+
- `Django`_ 2.2+
- `redis-py`_ 3.0+
- `Redis server`_ 2.8+

.. _Python: https://www.python.org/downloads/
.. _Django: https://www.djangoproject.com/download/
.. _redis-py: https://pypi.org/project/redis/
.. _Redis server: https://redis.io/download

User guide
----------

Installation
~~~~~~~~~~~~

Install with pip:

.. code-block:: console

    $ python -m pip install django-redis

Configure as cache backend
~~~~~~~~~~~~~~~~~~~~~~~~~~

To start using django-redis, you should change your Django cache settings to
something like:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }

django-redis uses the redis-py native URL notation for connection strings, it
allows better interoperability and has a connection string in more "standard"
way. Some examples:

- ``redis://[[username]:[password]]@localhost:6379/0``
- ``rediss://[[username]:[password]]@localhost:6379/0``
- ``unix://[[username]:[password]]@/path/to/socket.sock?db=0``

Three URL schemes are supported:

- ``redis://``: creates a normal TCP socket connection
- ``rediss://``: creates a SSL wrapped TCP socket connection
- ``unix://`` creates a Unix Domain Socket connection

There are several ways to specify a database number:

- A ``db`` querystring option, e.g. ``redis://localhost?db=0``
- If using the ``redis://`` scheme, the path argument of the URL, e.g.
  ``redis://localhost/0``

When using `Redis' ACLs <https://redis.io/topics/acl>`_, you will need to add the
username to the URL (and provide the password with the Cache ``OPTIONS``).
The login for the user ``django`` would look like this:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://django@localhost:6379/0",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PASSWORD": "mysecret"
            }
        }
    }

An alternative would be write both username and password into the URL:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://django:mysecret@localhost:6379/0",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }

In some circumstances the password you should use to connect Redis
is not URL-safe, in this case you can escape it or just use the
convenience option in ``OPTIONS`` dict:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PASSWORD": "mysecret"
            }
        }
    }

Take care, that this option does not overwrites the password in the uri, so if
you have set the password in the uri, this settings will be ignored.

Configure as session backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django can by default use any cache backend as session backend and you benefit
from that by using django-redis as backend for session storage without
installing any additional backends:

.. code-block:: python

    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

Testing with django-redis
~~~~~~~~~~~~~~~~~~~~~~~~~

django-redis supports customizing the underlying Redis client (see "Pluggable
clients"). This can be used for testing purposes.

In case you want to flush all data from the cache after a test, add the
following lines to your test class:

.. code-block:: python

    from django_redis import get_redis_connection

    def tearDown(self):
        get_redis_connection("default").flushall()

Advanced usage
--------------

Pickle version
~~~~~~~~~~~~~~

For almost all values, django-redis uses pickle to serialize objects.

The ``pickle.DEFAULT_PROTOCOL`` version of pickle is used by default to ensure safe upgrades and compatibility across Python versions.
If you want set a concrete version, you can do it, using ``PICKLE_VERSION`` option:

.. code-block:: python

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "PICKLE_VERSION": -1  # Will use highest protocol version available
            }
        }
    }

Socket timeout
~~~~~~~~~~~~~~

Socket timeout can be set using ``SOCKET_TIMEOUT`` and
``SOCKET_CONNECT_TIMEOUT`` options:

.. code-block:: python

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
                "SOCKET_TIMEOUT": 5,  # seconds
            }
        }
    }

``SOCKET_CONNECT_TIMEOUT`` is the timeout for the connection to be established
and ``SOCKET_TIMEOUT`` is the timeout for read and write operations after the
connection is established.

Compression support
~~~~~~~~~~~~~~~~~~~

django-redis comes with compression support out of the box, but is deactivated
by default. You can activate it setting up a concrete backend:

.. code-block:: python

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            }
        }
    }

Let see an example, of how make it work with *lzma* compression format:

.. code-block:: python

    import lzma

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "COMPRESSOR": "django_redis.compressors.lzma.LzmaCompressor",
            }
        }
    }

*Lz4* compression support (requires the lz4 library):

.. code-block:: python

    import lz4

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "COMPRESSOR": "django_redis.compressors.lz4.Lz4Compressor",
            }
        }
    }

*Zstandard (zstd)* compression support (requires the pyzstd library):

.. code-block:: python

    import pyzstd

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "COMPRESSOR": "django_redis.compressors.zstd.ZStdCompressor",
            }
        }
    }

Memcached exceptions behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In some situations, when Redis is only used for cache, you do not want
exceptions when Redis is down. This is default behavior in the memcached
backend and it can be emulated in django-redis.

For setup memcached like behaviour (ignore connection exceptions), you should
set ``IGNORE_EXCEPTIONS`` settings on your cache configuration:

.. code-block:: python

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "IGNORE_EXCEPTIONS": True,
            }
        }
    }

Also, you can apply the same settings to all configured caches, you can set the global flag in
your settings:

.. code-block:: python

    DJANGO_REDIS_IGNORE_EXCEPTIONS = True

Log Ignored Exceptions
~~~~~~~~~~~~~~~~~~~~~~

When ignoring exceptions with ``IGNORE_EXCEPTIONS`` or
``DJANGO_REDIS_IGNORE_EXCEPTIONS``, you may optionally log exceptions using the
global variable ``DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS`` in your settings file::

    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

If you wish to specify the logger in which the exceptions are output, simply
set the global variable ``DJANGO_REDIS_LOGGER`` to the string name and/or path
of the desired logger. This will default to ``__name__`` if no logger is
specified and ``DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS`` is ``True``::

    DJANGO_REDIS_LOGGER = 'some.specified.logger'

Infinite timeout
~~~~~~~~~~~~~~~~

django-redis comes with infinite timeouts support out of the box. And it
behaves in same way as django backend contract specifies:

- ``timeout=0`` expires the value immediately.
- ``timeout=None`` infinite timeout

.. code-block:: python

    cache.set("key", "value", timeout=None)

Get ttl (time-to-live) from key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With Redis, you can access to ttl of any stored key, for it, django-redis
exposes ``ttl`` function.

It returns:

- 0 if key does not exists (or already expired).
- None for keys that exists but does not have any expiration.
- ttl value for any volatile key (any key that has expiration).

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.set("foo", "value", timeout=25)
    >>> cache.ttl("foo")
    25
    >>> cache.ttl("not-existent")
    0

With Redis, you can access to ttl of any stored key in milliseconds, for it, django-redis
exposes ``pttl`` function.

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.set("foo", "value", timeout=25)
    >>> cache.pttl("foo")
    25000
    >>> cache.pttl("not-existent")
    0

Expire & Persist
~~~~~~~~~~~~~~~~

Additionally to the simple ttl query, you can send persist a concrete key or
specify a new expiration timeout using the ``persist`` and ``expire`` methods:

.. code-block:: pycon

    >>> cache.set("foo", "bar", timeout=22)
    >>> cache.ttl("foo")
    22
    >>> cache.persist("foo")
    True
    >>> cache.ttl("foo")
    None

.. code-block:: pycon

    >>> cache.set("foo", "bar", timeout=22)
    >>> cache.expire("foo", timeout=5)
    True
    >>> cache.ttl("foo")
    5

The ``expire_at`` method can be used to make the key expire at a specific moment in time.

.. code-block:: pycon

    >>> cache.set("foo", "bar", timeout=22)
    >>> cache.expire_at("foo", datetime.now() + timedelta(hours=1))
    True
    >>> cache.ttl("foo")
    3600

The ``pexpire_at`` method can be used to make the key expire at a specific moment in time with milliseconds precision:

.. code-block:: pycon

    >>> cache.set("foo", "bar", timeout=22)
    >>> cache.pexpire_at("foo", datetime.now() + timedelta(milliseconds=900, hours=1))
    True
    >>> cache.ttl("foo")
    3601
    >>> cache.pttl("foo")
    3600900

The ``pexpire`` method can be used to provide millisecond precision:

.. code-block:: pycon

    >>> cache.set("foo", "bar", timeout=22)
    >>> cache.pexpire("foo", timeout=5500)
    True
    >>> cache.pttl("foo")
    5500

Locks
~~~~~

It also supports the Redis ability to create Redis distributed named locks. The
Lock interface is identical to the ``threading.Lock`` so you can use it as
replacement.

.. code-block:: python

    with cache.lock("somekey"):
        do_some_thing()

Scan & Delete keys in bulk
~~~~~~~~~~~~~~~~~~~~~~~~~~

django-redis comes with some additional methods that help with searching or
deleting keys using glob patterns.

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.keys("foo_*")
    ["foo_1", "foo_2"]

A simple search like this will return all matched values. In databases with a
large number of keys this isn't suitable method. Instead, you can use the
``iter_keys`` function that works like the ``keys`` function but uses Redis
server side cursors. Calling ``iter_keys`` will return a generator that you can
then iterate over efficiently.

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.iter_keys("foo_*")
    <generator object algo at 0x7ffa9c2713a8>
    >>> next(cache.iter_keys("foo_*"))
    "foo_1"

For deleting keys, you should use ``delete_pattern`` which has the same glob
pattern syntax as the ``keys`` function and returns the number of deleted keys.

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.delete_pattern("foo_*")

Redis native commands
~~~~~~~~~~~~~~~~~~~~~

django-redis has limited support for some Redis atomic operations, such as the
commands ``SETNX`` and ``INCR``.

You can use the ``SETNX`` command through the backend ``set()`` method with the
``nx`` parameter:

.. code-block:: pycon

    >>> from django.core.cache import cache
    >>> cache.set("key", "value1", nx=True)
    True
    >>> cache.set("key", "value2", nx=True)
    False
    >>> cache.get("key")
    "value1"

Also, the ``incr`` and ``decr`` methods use Redis atomic operations when the
value that a key contains is suitable for it.

Raw client access
~~~~~~~~~~~~~~~~~

In some situations your application requires access to a raw Redis client to
use some advanced features that aren't exposed by the Django cache interface.
To avoid storing another setting for creating a raw connection, django-redis
exposes functions with which you can obtain a raw client reusing the cache
connection string: ``get_redis_connection(alias)``.

.. code-block:: pycon

    >>> from django_redis import get_redis_connection
    >>> con = get_redis_connection("default")
    >>> con
    <redis.client.Redis object at 0x2dc4510>

WARNING: Not all pluggable clients support this feature.

Connection pools
~~~~~~~~~~~~~~~~

Behind the scenes, django-redis uses the underlying redis-py connection pool
implementation, and exposes a simple way to configure it. Alternatively, you
can directly customize a connection/connection pool creation for a backend.

The default redis-py behavior is to not close connections, recycling them when
possible.

Configure default connection pool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default connection pool is simple. For example, you can customize the
maximum number of connections in the pool by setting ``CONNECTION_POOL_KWARGS``
in the ``CACHES`` setting:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            # ...
            "OPTIONS": {
                "CONNECTION_POOL_KWARGS": {"max_connections": 100}
            }
        }
    }

You can verify how many connections the pool has opened with the following
snippet:

.. code-block:: python

    from django_redis import get_redis_connection

    r = get_redis_connection("default")  # Use the name you have defined for Redis in settings.CACHES
    connection_pool = r.connection_pool
    print("Created connections so far: %d" % connection_pool._created_connections)

Since the default connection pool passes all keyword arguments it doesn't use
to its connections, you can also customize the connections that the pool makes
by adding those options to ``CONNECTION_POOL_KWARGS``:

.. code-block:: python

    CACHES = {
        "default": {
            # ...
            "OPTIONS": {
                "CONNECTION_POOL_KWARGS": {"max_connections": 100, "retry_on_timeout": True}
            }
        }
    }

Use your own connection pool subclass
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes you want to use your own subclass of the connection pool. This is
possible with django-redis using the ``CONNECTION_POOL_CLASS`` parameter in the
backend options.

.. code-block:: python

    from redis.connection import ConnectionPool

    class MyOwnPool(ConnectionPool):
        # Just doing nothing, only for example purpose
        pass

.. code-block:: python

    # Omitting all backend declaration boilerplate code.

    "OPTIONS": {
        "CONNECTION_POOL_CLASS": "myproj.mypool.MyOwnPool",
    }

Customize connection factory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If none of the previous methods satisfies you, you can get in the middle of the
django-redis connection factory process and customize or completely rewrite it.

By default, django-redis creates connections through the
``django_redis.pool.ConnectionFactory`` class that is specified in the global
Django setting ``DJANGO_REDIS_CONNECTION_FACTORY``.

.. code-block:: python

    class ConnectionFactory(object):
        def get_connection_pool(self, params: dict):
            # Given connection parameters in the `params` argument, return new
            # connection pool. It should be overwritten if you want do
            # something before/after creating the connection pool, or return
            # your own connection pool.
            pass

        def get_connection(self, params: dict):
            # Given connection parameters in the `params` argument, return a
            # new connection. It should be overwritten if you want to do
            # something before/after creating a new connection. The default
            # implementation uses `get_connection_pool` to obtain a pool and
            # create a new connection in the newly obtained pool.
            pass

        def get_or_create_connection_pool(self, params: dict):
            # This is a high layer on top of `get_connection_pool` for
            # implementing a cache of created connection pools. It should be
            # overwritten if you want change the default behavior.
            pass

        def make_connection_params(self, url: str) -> dict:
            # The responsibility of this method is to convert basic connection
            # parameters and other settings to fully connection pool ready
            # connection parameters.
            pass

        def connect(self, url: str):
            # This is really a public API and entry point for this factory
            # class. This encapsulates the main logic of creating the
            # previously mentioned `params` using `make_connection_params` and
            # creating a new connection using the `get_connection` method.
            pass

Use the sentinel connection factory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to facilitate using `Redis Sentinels`_, django-redis comes with a
built in sentinel connection factory, which creates sentinel connection pools.
In order to enable this functionality you should add the following:


.. code-block:: python

    # Enable the alternate connection factory.
    DJANGO_REDIS_CONNECTION_FACTORY = 'django_redis.pool.SentinelConnectionFactory'

    # These sentinels are shared between all the examples, and are passed
    # directly to redis Sentinel. These can also be defined inline.
    SENTINELS = [
        ('sentinel-1', 26379),
        ('sentinel-2', 26379),
        ('sentinel-3', 26379),
    ]

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            # The hostname in LOCATION is the primary (service / master) name
            "LOCATION": "redis://service_name/db",
            "OPTIONS": {
                # While the default client will work, this will check you
                # have configured things correctly, and also create a
                # primary and replica pool for the service specified by
                # LOCATION rather than requiring two URLs.
                "CLIENT_CLASS": "django_redis.client.SentinelClient",

                # Sentinels which are passed directly to redis Sentinel.
                "SENTINELS": SENTINELS,

                # kwargs for redis Sentinel (optional).
                "SENTINEL_KWARGS": {},

                # You can still override the connection pool (optional).
                "CONNECTION_POOL_CLASS": "redis.sentinel.SentinelConnectionPool",
            },
        },

        # A minimal example using the SentinelClient.
        "minimal": {
            "BACKEND": "django_redis.cache.RedisCache",

            # The SentinelClient will use this location for both the primaries
            # and replicas.
            "LOCATION": "redis://minimal_service_name/db",

            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.SentinelClient",
                "SENTINELS": SENTINELS,
            },
        },

        # A minimal example using the DefaultClient.
        "other": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": [
                # The DefaultClient is [primary, replicas...], but with the
                # SentinelConnectionPool it only requires one "is_master=0".
                "redis://other_service_name/db?is_master=1",
                "redis://other_service_name/db?is_master=0",
            ],
            "OPTIONS": {"SENTINELS": SENTINELS},
        },

        # A minimal example only using only replicas in read only mode (and
        # the DefaultClient).
        "readonly": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://readonly_service_name/db?is_master=0",
            "OPTIONS": {"SENTINELS": SENTINELS},
        },
    }

.. _Redis Sentinels: https://redis.io/topics/sentinel

Pluggable parsers
~~~~~~~~~~~~~~~~~

redis-py (the Python Redis client used by django-redis) comes with a pure
Python Redis parser that works very well for most common task, but if you want
some performance boost, you can use hiredis.

hiredis is a Redis client written in C and it has its own parser that can be
used with django-redis.

.. code-block:: python

    "OPTIONS": {
        "PARSER_CLASS": "redis.connection.HiredisParser",
    }

Pluggable clients
~~~~~~~~~~~~~~~~~

django-redis is designed for to be very flexible and very configurable. For it,
it exposes a pluggable backends that make easy extend the default behavior, and
it comes with few ones out the box.

Default client
^^^^^^^^^^^^^^

Almost all about the default client is explained, with one exception: the
default client comes with replication support.

To connect to a Redis replication setup, you should change the ``LOCATION`` to
something like:

.. code-block:: python

    "LOCATION": [
        "redis://127.0.0.1:6379/1",
        "redis://127.0.0.1:6378/1",
    ]

The first connection string represents the primary server and the rest to
replica servers.

WARNING: Replication setup is not heavily tested in production environments.

Shard client
^^^^^^^^^^^^

This pluggable client implements client-side sharding. It inherits almost all
functionality from the default client. To use it, change your cache settings to
something like this:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": [
                "redis://127.0.0.1:6379/1",
                "redis://127.0.0.1:6379/2",
            ],
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.ShardClient",
            }
        }
    }

WARNING: Shard client is still experimental, so be careful when using it in
production environments.

Herd client
^^^^^^^^^^^

This pluggable client helps dealing with the thundering herd problem. You can read more about it
on link: `Wikipedia <http://en.wikipedia.org/wiki/Thundering_herd_problem>`_

Like previous pluggable clients, it inherits all functionality from the default client, adding some
additional methods for getting/setting keys.

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.HerdClient",
            }
        }
    }

This client exposes additional settings:

- ``CACHE_HERD_TIMEOUT``: Set default herd timeout. (Default value: 60s)

Pluggable serializer
~~~~~~~~~~~~~~~~~~~~

The pluggable clients serialize data before sending it to the server. By
default, django-redis serializes the data using the Python ``pickle`` module.
This is very flexible and can handle a large range of object types.

To serialize using JSON instead, the serializer ``JSONSerializer`` is also
available.

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            }
        }
    }

There's also support for serialization using `MsgPack`_ (that requires the
msgpack library):

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SERIALIZER": "django_redis.serializers.msgpack.MSGPackSerializer",
            }
        }
    }

.. _MsgPack: http://msgpack.org/

Pluggable Redis client
~~~~~~~~~~~~~~~~~~~~~~

django-redis uses the Redis client ``redis.client.StrictClient`` by default. It
is possible to use an alternative client.

You can customize the client used by setting ``REDIS_CLIENT_CLASS`` in the
``CACHES`` setting. Optionally, you can provide arguments to this class by
setting ``REDIS_CLIENT_KWARGS``.

.. code-block:: python

    CACHES = {
        "default": {
            "OPTIONS": {
                "REDIS_CLIENT_CLASS": "my.module.ClientClass",
                "REDIS_CLIENT_KWARGS": {"some_setting": True},
            }
        }
    }


Closing Connections
~~~~~~~~~~~~~~~~~~~

The default django-redis behavior on close() is to keep the connections to Redis server.

You can change this default behaviour for all caches by the ``DJANGO_REDIS_CLOSE_CONNECTION = True``
in the django settings (globally) or (at cache level) by setting ``CLOSE_CONNECTION: True`` in the ``OPTIONS``
for each configured cache.

Setting True as a value will instruct the django-redis to close all the connections (since v. 4.12.2), irrespectively of its current usage.

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CLOSE_CONNECTION": True,
            }
        }
    }

SSL/TLS and Self-Signed certificates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In case you encounter a Redis server offering a TLS connection using a
self-signed certificate you may disable certification verification with the
following:

.. code-block:: python

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "rediss://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None}
            }
        }
    }


License
-------

.. code-block:: text

    Copyright (c) 2011-2015 Andrey Antukh <niwi@niwi.nz>
    Copyright (c) 2011 Sean Bleier

    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met:
    1. Redistributions of source code must retain the above copyright
       notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.
    3. The name of the author may not be used to endorse or promote products
       derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS`` AND ANY EXPRESS OR
    IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
    OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
    IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
    INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
    NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
    THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
