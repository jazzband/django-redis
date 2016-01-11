# This is an example test settings file for use with the Django test suite.
#
# The 'sqlite3' backend requires only the ENGINE setting (an in-
# memory database will be used). All other backends will require a
# NAME and potentially authentication information. See the
# following section in the docs for more information:
#
# https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/unit-tests/
#
# The different databases that Django supports behave differently in certain
# situations, so it is recommended to run the test suite against as many
# database backends as possible.  You may want to create a separate settings
# file for each of the backends you test against.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3'
    },
}

SECRET_KEY = "django_tests_secret_key"
TIME_ZONE = 'America/Chicago'
LANGUAGE_CODE = 'en-us'
ADMIN_MEDIA_PREFIX = '/static/admin/'
STATICFILES_DIRS = ()

MIDDLEWARE_CLASSES = []

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': [
            '127.0.0.1:6379:5',
        ],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.HerdClient',
        }
    },
    'doesnotexist': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': '127.0.0.1:56379:1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.HerdClient',
        }
    },
    'sample': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': '127.0.0.1:6379:1,127.0.0.1:6379:1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.HerdClient',
        }
    },
    "with_prefix": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "127.0.0.1:6379:1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.HerdClient",
        },
        "KEY_PREFIX": "test-prefix",
    },
}

# TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'

INSTALLED_APPS = (
    "django.contrib.sessions",
    'redis_backend_testapp',
    'hashring_test',
)
