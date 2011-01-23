from distutils.core import setup

setup(
    name = "django-redis-cache",
    url = "http://github.com/sebleier/django-redis-cache/",
    author = "Sean Bleier",
    author_email = "sebleier@gmail.com",
    version = "0.5.0",
    packages = ["redis_cache"],
    description = "Redis Cache Backend for Django",
    classifiers = [
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "Environment :: Web Environment",
        "Framework :: Django",
    ],
)
