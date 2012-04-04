#!/usr/bin/env python

import os
import sys
import shutil
import tempfile


ALWAYS_INSTALLED_APPS = ['redis_backend_testapp']
RUNTESTS_DIR = os.path.dirname(__file__)
TEMP_DIR = tempfile.mkdtemp(prefix='redis_cache_')

os.environ['DJANGO_TEST_TEMP_DIR'] = TEMP_DIR
sys.path.insert(0, os.path.join(RUNTESTS_DIR, '..'))

def setup(verbosity, test_labels):
    from django.conf import settings
    state = {
        'INSTALLED_APPS': settings.INSTALLED_APPS,
        'ROOT_URLCONF': getattr(settings, "ROOT_URLCONF", ""),
        'TEMPLATE_DIRS': settings.TEMPLATE_DIRS,
        'USE_I18N': settings.USE_I18N,
        'LOGIN_URL': settings.LOGIN_URL,
        'LANGUAGE_CODE': settings.LANGUAGE_CODE,
        'MIDDLEWARE_CLASSES': settings.MIDDLEWARE_CLASSES,
        'STATIC_URL': settings.STATIC_URL,
        'STATIC_ROOT': settings.STATIC_ROOT,
    }

    # Redirect some settings for the duration of these tests.
    settings.INSTALLED_APPS = ALWAYS_INSTALLED_APPS
    settings.ROOT_URLCONF = 'urls'
    settings.STATIC_URL = '/static/'
    settings.STATIC_ROOT = os.path.join(TEMP_DIR, 'static')
    #settings.TEMPLATE_DIRS = (os.path.join(RUNTESTS_DIR, TEST_TEMPLATE_DIR),)
    settings.USE_I18N = True
    settings.LANGUAGE_CODE = 'en'
    settings.LOGIN_URL = '/accounts/login/'
    settings.MIDDLEWARE_CLASSES = (
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
    )
    settings.SITE_ID = 1
    # For testing comment-utils, we require the MANAGERS attribute
    # to be set, so that a test email is sent out which we catch
    # in our tests.
    settings.MANAGERS = ("niwi@niwi.be",)

    settings.CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': '/tmp/redis.sock',
            'OPTIONS': {
                'DB': 15,
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            }
        }
    }

    # Load all the ALWAYS_INSTALLED_APPS.
    # (This import statement is intentionally delayed until after we
    # access settings because of the USE_I18N dependency.)
    from django.db.models.loading import get_apps, load_app
    get_apps()

    return state

def teardown(state):
    from django.conf import settings
    # Removing the temporary TEMP_DIR. Ensure we pass in unicode
    # so that it will successfully remove temp trees containing
    # non-ASCII filenames on Windows. (We're assuming the temp dir
    # name itself does not contain non-ASCII characters.)
    shutil.rmtree(unicode(TEMP_DIR))
    # Restore the old settings.
    for key, value in state.items():
        setattr(settings, key, value)


def django_tests(verbosity, interactive, failfast, test_labels):
    from django.conf import settings
    state = setup(verbosity, test_labels)
    extra_tests = []

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    if not hasattr(settings, 'TEST_RUNNER'):
        settings.TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner'
    TestRunner = get_runner(settings)

    test_runner = TestRunner(verbosity=verbosity, interactive=interactive,
        failfast=failfast)
    failures = test_runner.run_tests(test_labels, extra_tests=extra_tests)

    teardown(state)
    return failures


if __name__ == "__main__":
    from optparse import OptionParser
    usage = "%prog [options] [module module module ...]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        '-v','--verbosity', action='store', dest='verbosity', default='1',
        type='choice', choices=['0', '1', '2', '3'],
        help='Verbosity level; 0=minimal output, 1=normal output, 2=all '
             'output')
    parser.add_option(
        '--noinput', action='store_false', dest='interactive', default=True,
        help='Tells Django to NOT prompt the user for input of any kind.')
    parser.add_option(
        '--failfast', action='store_true', dest='failfast', default=False,
        help='Tells Django to stop running the test suite after first failed '
             'test.')
    parser.add_option(
        '--settings',
        help='Python path to settings module, e.g. "myproject.settings". If '
             'this isn\'t provided, the DJANGO_SETTINGS_MODULE environment '
             'variable will be used.')
    parser.add_option(
        '--liveserver', action='store', dest='liveserver', default=None,
        help='Overrides the default address where the live server (used with '
             'LiveServerTestCase) is expected to run from. The default value '
             'is localhost:8081.'),
    options, args = parser.parse_args()
    if options.settings:
        os.environ['DJANGO_SETTINGS_MODULE'] = options.settings
    elif "DJANGO_SETTINGS_MODULE" not in os.environ:
        parser.error("DJANGO_SETTINGS_MODULE is not set in the environment. "
                      "Set it or use --settings.")
    else:
        options.settings = os.environ['DJANGO_SETTINGS_MODULE']

    if options.liveserver is not None:
        os.environ['DJANGO_LIVE_TEST_SERVER_ADDRESS'] = options.liveserver

    failures = django_tests(int(options.verbosity), options.interactive,
                            options.failfast, args)
    if failures:
        sys.exit(bool(failures))
