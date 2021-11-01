Running the test suite
----------------------

.. code-block:: bash

  # start redis and a sentinel (uses docker with image redis:latest)
  PRIMARY=$(tests/start_redis.sh)
  SENTINEL=$(tests/start_redis.sh --sentinel)

  # or just wait 5 - 10 seconds and most likely this would be the case
  tests/wait_for_redis.sh $PRIMARY 6379
  tests/wait_for_redis.sh $SENTINEL 26379

  # run the tests
  tox

  # shut down redis
for container in $PRIMARY $SENTINEL; do
  docker stop $container && docker rm $container
done
