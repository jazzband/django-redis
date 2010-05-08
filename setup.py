#!/usr/bin/env python

from distutils.core import setup

version = "0.2a1"

classifiers = [
    "Programming Language :: Python",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
    "Environment :: Web Environment",
    "Framework :: Django",
]

setup(
    name = "django-redis-cache",
    version = version,
    url = "http://github.com/blackbrrr/django-redis-cache/",
    author = "Matt Dennewitz",
    author_email = "mattdennewitz@gmail.com",
    packages = ["redis_cache"],
    description = "Redis Cache Backend for Django",
    classifiers = classifiers
)

