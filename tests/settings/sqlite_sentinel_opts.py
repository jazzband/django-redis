SECRET_KEY = "django_tests_secret_key"

SENTINELS = [("127.0.0.1", 26379)]

conn_factory = "django_redis.pool.SentinelConnectionFactory"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://default_service?db=5"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
            "CONNECTION_FACTORY": conn_factory,
        },
    },
    "doesnotexist": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://missing_service?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
            "CONNECTION_FACTORY": conn_factory,
        },
    },
    "sample": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://default_service?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "SENTINELS": SENTINELS,
            "CONNECTION_FACTORY": conn_factory,
        },
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://default_service?db=1",
        "KEY_PREFIX": "test-prefix",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
            "CONNECTION_FACTORY": conn_factory,
        },
    },
}

INSTALLED_APPS = ["django.contrib.sessions"]

USE_TZ = False
