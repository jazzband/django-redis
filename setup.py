from setuptools import setup

description = """
Redis Cache Backend for Django. (This is fork of django-redis-cache)
"""

setup(
    name = "django-redis",
    url = "https://github.com/niwibe/django-redis",
    author = "Andrei Antoukh",
    author_email = "niwi@niwi.be",
    version='3.0',
    packages = [
        "redis_cache",
        "redis_cache.stats"
    ],
    description = description.strip(),
    install_requires=[
        'redis>=2.7.0',
    ],
    zip_safe=False,
    include_package_data = True,
    package_data = {
        '': ['*.html'],
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
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
