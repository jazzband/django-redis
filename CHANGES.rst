Changelog
=========

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

