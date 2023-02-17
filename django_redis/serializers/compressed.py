from django.utils.encoding import force_bytes

import lzma


class CompressedMixin:
    def serialize(self, value):
        return lzma.compress(force_bytes(super(CompressedMixin, self).serialize(value)))

    def deserialize(self, value):
        return super(CompressedMixin, self).deserialize(lzma.decompress(value))
