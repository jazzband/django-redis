Preparing a Release
===================

The following steps are needed to prepare a release:

1. Make sure the VERSION in ``django_redis/__init__.py`` has been updated.
2. Run ``towncrier build`` to update the ``CHANGELOG.rst`` with the
   news fragments for the release.
3. Commit the changes for steps 1 and 2.
4. Tag the commit with the same version as specified for VERSION in step 1.
5. Wait for the `release action`_ to complete, which will upload the package
   to `django-redis jazzband`_, and when it's complete you can then release
   the package to PyPI.

.. _release action: https://github.com/jazzband/django-redis/actions/workflows/release.yml
.. _django-redis jazzband: https://jazzband.co/projects/django-redis
