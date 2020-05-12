import pickle
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from .base import BaseSerializer


class PickleSerializer(BaseSerializer):
    def __init__(self, options) -> None:
        self._pickle_version = -1
        self.setup_pickle_version(options)

    def setup_pickle_version(self, options) -> None:
        if "PICKLE_VERSION" in options:
            try:
                self._pickle_version = int(options["PICKLE_VERSION"])
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def dumps(self, value) -> bytes:
        return pickle.dumps(value, self._pickle_version)

    def loads(self, value) -> Any:
        return pickle.loads(value)
