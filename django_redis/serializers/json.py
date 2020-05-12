import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from .base import BaseSerializer


class JSONSerializer(BaseSerializer):
    encoder_class = DjangoJSONEncoder

    def dumps(self, value) -> bytes:
        return json.dumps(value, cls=self.encoder_class).encode()

    def loads(self, value) -> Any:
        return json.loads(value.decode())
