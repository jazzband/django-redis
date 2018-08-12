from setuptools import setup

from django_redis import __version__

description = """
Full featured redis cache backend for Django.
"""

setup(
    name="django-redis",
    url="https://github.com/niwibe/django-redis",
    author="Andrei Antoukh",
    author_email="niwi@niwi.nz",
    version=__version__,
    packages=[
        "django_redis",
        "django_redis.client",
        "django_redis.serializers",
        "django_redis.compressors"
    ],
    description=description.strip(),
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
    install_requires=[
        "Django>=1.11",
        "redis>=2.10.0",
    ],
    zip_safe=False,
    include_package_data=True,
    package_data={
        "": ["*.html"],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 1.11",
        "Framework :: Django :: 2.0",
        "Framework :: Django :: 2.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
