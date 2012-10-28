from setuptools import setup

description = """
Redis Cache Backend for Django. (This is fork of django-redis-cache)
"""

setup(
    name = "django-redis",
    url = "https://github.com/niwibe/django-redis",
    author = "Andrei Antoukh",
    author_email = "niwi@niwi.be",
    version='2.2.2',
    packages = [
        "redis_cache",
        "redis_cache.stats"
    ],
    description = description.strip(),
    install_requires=[
        'redis>=2.4.5',
    ],
    zip_safe=False,
    include_package_data = True,
    package_data = {
        '': ['*.html'],
    },
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "Environment :: Web Environment",
        "Framework :: Django",
    ],
)
