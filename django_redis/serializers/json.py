import json

from django.core.serializers.json import DjangoJSONEncoder

from .base import BaseSerializer


class JSONSerializer(BaseSerializer):
    encoder_class = DjangoJSONEncoder

    def dumps(self, value):
        return json.dumps(value, cls=self.encoder_class).encode()

    def loads(self, value):
        return json.loads(value.decode())
