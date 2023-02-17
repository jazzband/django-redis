from .compressed import CompressedMixin
from .json import JSONSerializer


class CompressedJSONSerializer(CompressedMixin, JSONSerializer):
    pass
