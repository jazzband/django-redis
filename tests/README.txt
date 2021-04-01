Test requirements
-----------------

Python packages
~~~~~~~~~~~~~~~

Install the development requirements using the requirements.txt file:

    pip install -r requirements.txt

redis
~~~~~

* redis listening on default socket 127.0.0.1:6379
* for runtests-sentinel.py: redis sentinel listening on default socket
  127.0.0.1:26379 with the following config:

    sentinel monitor default_service 127.0.0.1 6379 1
    sentinel down-after-milliseconds default_service 3200
    sentinel failover-timeout default_service 10000
    sentinel parallel-syncs default_service 1

After this, run this command:

    python runtests.py
    python runtests.py <test_file>.<TestClass>.<MethodName>
