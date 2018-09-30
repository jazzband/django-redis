# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import dill

from django.core.exceptions import ImproperlyConfigured

from .base import BaseSerializer


class DillSerializer(BaseSerializer):
    def __init__(self, options):
        self._pickle_version = -1
        self.setup_pickle_version(options)

    def setup_pickle_version(self, options):
        if "PICKLE_VERSION" in options:
            try:
                self._pickle_version = int(options["PICKLE_VERSION"])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def dumps(self, value):
        return dill.dumps(value, self._pickle_version)

    def loads(self, value):
        return dill.loads(value)
