Changelog
=========

Version 3.0
-----------
Not yet released.

- Python 3.2+ support.
- Drop support for django < 1.4.2
- Master-Slave connections.
- Code cleaning and refactor.
- Auto failover.

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

