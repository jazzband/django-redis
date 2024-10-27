Running the test suite
----------------------

.. code-block:: bash

  # start redis and a sentinel (uses docker with image redis:latest)
docker compose -f docker/docker-compose.yml up -d --wait