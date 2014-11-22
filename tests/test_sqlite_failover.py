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
        'LOCATION': '127.0.0.1:6379:1/127.0.0.1:6380:1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.SimpleFailoverClient',
        }
    },
}

# TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'

INSTALLED_APPS = (
    'redis_backend_testapp',
    'hashring_test',
)
