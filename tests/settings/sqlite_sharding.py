SECRET_KEY = "django_tests_secret_key"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://127.0.0.1:6379?db=9", "redis://127.0.0.1:6379?db=10"],
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.ShardClient"},
    },
    "doesnotexist": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://127.0.0.1:56379?db=9", "redis://127.0.0.1:56379?db=10"],
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.ShardClient"},
    },
    "sample": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=9,redis://127.0.0.1:6379?db=9",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.ShardClient"},
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=9",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.ShardClient"},
        "KEY_PREFIX": "test-prefix",
    },
}

INSTALLED_APPS = ["django.contrib.sessions"]

USE_TZ = False
