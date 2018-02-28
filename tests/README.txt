Test requirements
-----------------

Python packages
~~~~~~~~~~~~~~~

Install the development requirements using the requirements.txt file:

    pip install -r requirements.txt

redis
~~~~~

* redis listening on default socket 127.0.0.1:6379

After this, run this command:

    python runtests.py
    python runtests.py <test_file>.<TestClass>.<MethodName>
