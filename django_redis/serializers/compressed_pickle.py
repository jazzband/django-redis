from .compressed import CompressedMixin
from .pickle import PickleSerializer


class CompressedPickleSerializer(CompressedMixin, PickleSerializer):
    pass
