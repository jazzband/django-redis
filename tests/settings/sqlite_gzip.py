SECRET_KEY = "django_tests_secret_key"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": ["redis://127.0.0.1:6379?db=2", "redis://127.0.0.1:6379?db=2"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.gzip.GzipCompressor",
        },
    },
    "doesnotexist": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:56379?db=2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.gzip.GzipCompressor",
        },
    },
    "sample": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=2,redis://127.0.0.1:6379?db=2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.gzip.GzipCompressor",
        },
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.gzip.GzipCompressor",
        },
        "KEY_PREFIX": "test-prefix",
    },
}

INSTALLED_APPS = ["django.contrib.sessions"]

USE_TZ = False
