from distutils.core import setup

setup(
    name = "django-redis-cache",
    url = "http://github.com/blackbrrr/django-redis-cache/",
    author = "Matt Dennewitz",
    author_email = "mattdennewitz@gmail.com",
    version = "0.2a3",
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

