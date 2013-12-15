Changelog
=========

Version 3.4.0
-------------

- Fix exception name from ConnectionInterrumped to
  ConnectionInterrupted mantaining a old exception class
  for backward compatibility (thanks Łukasz Langa (@ambv))

- Fix wrong behavior for "default" parameter on get method
  when DJANGO_REDIS_IGNORE_EXCEPTIONS is True
  (also thansk to Łukasz Langa (@ambv)).

- Now added support for master-slave connection to default
  client (it still experimental because is not tested in
  production environments).

- Merged SimpleFailoverClient experimental client (only for
  experiment with it, not ready for use in production)

- Django 1.6 cache changes compatibility. Explicitly passing in
  timeout=None no longer results in using the default timeout.

- Major code cleaning. (Thanks to Bertrand Bordage @BertrandBordage)


Version 3.3.0
-------------

- Add SOCKET_TIMEOUT attribute to OPTIONS (thanks to @eclipticplane)

Version 3.2.0
-------------

- Changed default behavior of connection error exceptions: now by default
    raises exception on connection error is occured.

Thanks to Mümin Öztürk:

- cache.add now uses setnx redis command (atomic operation)
- cache.incr and cache.decr now uses redis incrby command (atomic operation)


Version 3.1.7
-------------

- Fix python3 compatibility on utils module.

Version 3.1.6
-------------

- Add nx argument on set method for both clients (thanks to Kirill Zaitsev)

Version 3.1.5
-------------

- Bug fixes on sharded client.

Version 3.1.4
-------------

- Now reuse connection pool on masive use of `get_cache` method.

Version 3.1.3
-------------

- Fixed python 2.6 compatibility.

Version 3.1.2
-------------

- Now on call close() not disconnect all connection pool.

Version 3.1.1
-------------

- Fixed incorrect exception message on LOCATION has wrong format.
    (Thanks to Yoav Weiss)

Version 3.1
-----------

- Helpers for access to raw redis connection.

Version 3.0
-----------

- Python 3.2+ support.
- Code cleaning and refactor.
- Ignore exceptiosn (same behavior as memcached backend)
- Pluggable clients.
- Unified connection string.


Version 2.2.2
-------------

- Bug fixes on ``keys`` and ``delete_pattern`` methods.


Version 2.2.1
-------------

- Remove duplicate check if key exists on ``incr`` method.
- Fix incorrect behavior of ``delete_pattern`` with sharded client.


Version 2.2
-----------

- New ``delete_pattern`` method. Useful for delete keys using wildcard syntax.


Version 2.1
-----------

- Many bug fixes.
- Client side sharding.

