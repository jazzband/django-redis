Usage of cache backend
======================

To start using django-redis, you must change your django cache settings. django-redis implements the standard interface for django cache backends.

With django-redis 3.0 has introduced certain changes, not backwards compatible, in part redis connection settings. The ``LOCATION`` string must be have always three colons instead of two.

Old way (django-redis < 3.0):

.. code-block:: python

    CACHES = {
        #...
        "LOCATION": "ip:port",
        "OPTIONS": {
            "DB": 1
        }
    }

New way:

.. code-block:: python

    CACHES = {
        #...
        "LOCATION": "ip:port:db",
    }


This is the complete example:

.. code-block:: python

    CACHES = {
        "LOCATION": "127.0.0.1:6379:1",
        "OPTIONS": {
            "CLIENT_CLASS": "redis_cache.client.DefaultClient",
        }
    }
