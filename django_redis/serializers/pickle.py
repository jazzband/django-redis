import pickle
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from .base import BaseSerializer


class PickleSerializer(BaseSerializer):
    def __init__(self, options) -> None:
        self._pickle_version = pickle.DEFAULT_PROTOCOL
        self.setup_pickle_version(options)

        super().__init__(options=options)

    def setup_pickle_version(self, options) -> None:
        if "PICKLE_VERSION" in options:
            try:
                self._pickle_version = int(options["PICKLE_VERSION"])
                if self._pickle_version > pickle.HIGHEST_PROTOCOL:
                    raise ImproperlyConfigured(
                        f"PICKLE_VERSION can't be higher than pickle.HIGHEST_PROTOCOL:"
                        f" {pickle.HIGHEST_PROTOCOL}"
                    )
            except (ValueError, TypeError):
                raise ImproperlyConfigured("PICKLE_VERSION value must be an integer")

    def dumps(self, value: Any) -> bytes:
        return pickle.dumps(value, self._pickle_version)

    def loads(self, value: bytes) -> Any:
        return pickle.loads(value)
