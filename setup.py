from setuptools import setup

description = """
Full featured redis cache backend for Django.
"""

setup(
    name = "django-redis",
    url = "https://github.com/niwibe/django-redis",
    author = "Andrei Antoukh",
    author_email = "niwi@niwi.be",
    version="4.1.0",
    packages = [
        "django_redis",
        "django_redis.client",
        "django_redis.serializers"
    ],
    description = description.strip(),
    install_requires=[
        "redis>=2.10.0",
        "msgpack-python>=0.4.6"
    ],
    zip_safe=False,
    include_package_data = True,
    package_data = {
        "": ["*.html"],
    },
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Operating System :: OS Independent",
        "Environment :: Web Environment",
        "Framework :: Django",
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
