Running the test suite
----------------------

.. code-block:: bash

  # start redis and a sentinel (uses docker with image redis:alpine)
docker compose -f tests/compose.yml up --detach --wait
