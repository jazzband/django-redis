SECRET_KEY = "django_tests_secret_key"

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': [
            '127.0.0.1:6379:1',
            '127.0.0.1:6379:2',
        ],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.ShardClient',
        }
    },
    'doesnotexist': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': [
            "redis://127.0.0.1:56379?db=1",
            "redis://127.0.0.1:56379?db=2",
        ],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.ShardClient',
        }
    },
    'sample': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': '127.0.0.1:6379:1,127.0.0.1:6379:1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.ShardClient',
        }
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379?db=1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.ShardClient",
        },
        "KEY_PREFIX": "test-prefix",
    },
}

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

INSTALLED_APPS = (
    "django.contrib.sessions",
)
