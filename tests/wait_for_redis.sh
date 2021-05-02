#!/bin/bash

CONTAINER=$1
PORT=$2

for i in {1..60}; do
  if docker inspect "$CONTAINER" \
      --format '{{.State.Health.Status}}' \
        | grep -q starting; then
    sleep 1
  else
    if ! nc -z 127.0.0.1 $PORT &>/dev/null; then
      echo >&2 "Port $PORT does not seem to be open, redis will not work with docker rootless!"
    fi
    # exit successfully in case nc was not found or -z is not supported
    exit 0
  fi
done

echo >&2 "Redis did not seem to start in ~60s, aborting"
exit 1
