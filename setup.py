from setuptools import setup

description = """
Redis Cache Backend for Django. (This is fork of django-redis-cache)
"""

setup(
    name = "django-redis",
    url = "https://github.com/niwibe/django-redis",
    author = "Andrei Antoukh",
    author_email = "niwi@niwi.be",
    version=':versiontools:redis_cache:',
    packages = [
        "redis_cache", 
        "redis_cache.stats"
    ],
    description = description.strip(),
    install_requires=[
        'distribute',
        'redis>=2.4.5',
        'hiredis>=0.1.0',
    ],
    setup_requires = [
        'versiontools >= 1.8',
    ],
    zip_safe=False,
    classifiers = [
        'Development Status :: 4 - Beta',
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "Environment :: Web Environment",
        "Framework :: Django",
    ],
)
