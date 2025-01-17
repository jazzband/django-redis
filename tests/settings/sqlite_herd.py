SECRET_KEY = "django_tests_secret_key"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://127.0.0.1:6379?db=3"],
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.HerdClient"},
    },
    "doesnotexist": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:56379?db=3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.HerdClient"},
    },
    "sample": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=3,redis://127.0.0.1:6379?db=3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.HerdClient"},
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.HerdClient"},
        "KEY_PREFIX": "test-prefix",
    },
}

INSTALLED_APPS = ["django.contrib.sessions"]

USE_TZ = False

CACHE_HERD_TIMEOUT = 2
