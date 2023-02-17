from .compressed import CompressedMixin
from .msgpack import MSGPackSerializer


class CompressedMSGPackSerializer(CompressedMixin, MSGPackSerializer):
    pass
