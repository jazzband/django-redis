SECRET_KEY = "django_tests_secret_key"

DJANGO_REDIS_CONNECTION_FACTORY = "django_redis.pool.SentinelConnectionFactory"

SENTINELS = [("127.0.0.1", 26379)]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://default_service?db=5"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
        },
    },
    "doesnotexist": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://missing_service?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
        },
    },
    "sample": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://default_service?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "SENTINELS": SENTINELS,
        },
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://default_service?db=1",
        "KEY_PREFIX": "test-prefix",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SENTINELS": SENTINELS,
        },
    },
}

# TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'

INSTALLED_APPS = ["django.contrib.sessions"]
