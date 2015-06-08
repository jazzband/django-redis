Test requirements
-----------------

python packages
~~~~~~~~~~~~~~~

the following packages can be installed with pip

* redis (https://github.com/andymccurdy/redis-py)
* hiredis (https://github.com/redis/hiredis)
* django (https://www.djangoproject.com/)
* msgpack-python (http://msgpack.org/)

redis
~~~~~

* redis listening on default socket 127.0.0.1:6379

After this, run this command:

    python runtests.py
    python runtests.py <appName>.<TestClass>.<MethodName>
