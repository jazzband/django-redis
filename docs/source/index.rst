.. django-redis documentation master file, created by
   sphinx-quickstart on Sun Oct 28 10:52:46 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

django-redis
============

It is a fork of django-redis-cache. And the reasons are: The author seems to have abandoned the project and has significant bugs that have not been fixed.

Description
-----------

Redis cache allows you to use either a TCP connection or Unix domain socket to connect to your redis server. Using a TCP connection is useful for when you have your redis server separate from your app server and/or within a distributed environment. Unix domain sockets are useful if you have your redis server and application running on the same machine and want the fastest possible connection.

You can specify (optionally) what parser class you want redis-py to use when parsing messages from the redis server. redis-py will pick the best parser for you implicitly, but using the PARSER_CLASS setting gives you control and the option to roll your own parser class if you are so bold.

This cache backend requires the redis-py python client library for communicating with the Redis server.

Features
--------

* In active development.
* Sharding supported in a single package.
* Complete battery of tests (accepting improvements).
* Used in production environments on several projects.
* Can set keys with infinite timeout: cache.set('key', 'value', timeout=0)
* Python 3.2+ support. (under development, coming soon with 3.0)
* Master-Slave connections. (under development, coming soon with 3.0)
* Auto failover to other cache backends. (under development, coming soon with 3.0)


Contents
--------

.. toctree::
    :maxdepth: 1

    setup.rst
    sharding.rst
    auto-failover.rst
    changelog.rst


How to install?
---------------

Run ``python setup.py install`` to install, or place ``redis_cache`` on your Python path.

You can also install it with: ``pip install django-redis``


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
