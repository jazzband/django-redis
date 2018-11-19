SECRET_KEY = "django_tests_secret_key"

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': [
            'unix:/tmp/redis.sock:1',
            'unix:/tmp/redis.sock:1',
        ],
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
        }
    },
    'doesnotexist': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:56379?db=1',
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
        }
    },
    'sample': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '127.0.0.1:6379:1,127.0.0.1:6379:1',
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
        }
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "test-prefix",
    },
}

TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'

INSTALLED_APPS = (
    "django.contrib.sessions",
)
