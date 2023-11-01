#!/bin/bash

# This command will start redis for both the CI and for local testing

if ! command -v docker &> /dev/null; then
  echo >&2 "Docker is required but was not found."
  exit 1
fi

ARGS=()
PORT=6379
SENTINEL=0
while (($# > 0)); do
  case "$1" in
    --sentinel)
      # setup a redis sentinel
      CONF=$(mktemp -d)
      ARGS=("${ARGS[@]}" "$CONF/redis.conf" --sentinel)
      PORT=26379
      SENTINEL=1

      cat > "$CONF/redis.conf" <<EOF
sentinel monitor default_service 127.0.0.1 6379 1
sentinel down-after-milliseconds default_service 3200
sentinel failover-timeout default_service 10000
sentinel parallel-syncs default_service 1
EOF

      chmod 777 "$CONF"
      chmod 666 "$CONF/redis.conf"

      shift
      ;;
  esac
done

# open a unix socket for socket tests
if [[ $SENTINEL == 0 ]]; then
  # make sure the file doesn't already exist
  rm -f /tmp/redis.sock
  ARGS=("${ARGS[@]}" --unixsocket /tmp/redis.sock --unixsocketperm 777)
fi

# start redis
docker run \
  --health-cmd "redis-cli -p $PORT:$PORT ping" \
  --health-interval 10s \
  --health-retries 5 \
  --health-timeout 5s \
  --user $(id -u):$(id -g) \
  --publish $PORT:$PORT \
  --volume /tmp:/tmp \
  --detach redis:latest redis-server "${ARGS[@]}"
