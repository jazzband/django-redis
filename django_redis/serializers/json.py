# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.encoding import force_bytes, force_text

from .base import BaseSerializer


class JSONSerializer(BaseSerializer):
    def dumps(self, value):
        return force_bytes(json.dumps(value, cls=DjangoJSONEncoder))

    def loads(self, value):
        return json.loads(force_text(value))
