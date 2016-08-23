from setuptools import setup

from django_redis import __version__


description = """
Full featured redis cache backend for Django.
"""

setup(
    name = "django-redis",
    url = "https://github.com/niwibe/django-redis",
    author = "Andrei Antoukh",
    author_email = "niwi@niwi.nz",
    version=__version__,
    packages = [
        "django_redis",
        "django_redis.client",
        "django_redis.serializers",
        "django_redis.compressors"
    ],
    description = description.strip(),
    install_requires=[
        "redis>=2.10.0",
    ],
    zip_safe=False,
    include_package_data = True,
    package_data = {
        "": ["*.html"],
    },
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django :: 1.8",
        "Framework :: Django :: 1.9",
        "Framework :: Django :: 1.10",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
