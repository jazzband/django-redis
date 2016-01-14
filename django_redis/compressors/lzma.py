# -*- coding: utf-8 -*-

from __future__ import absolute_import

import lzma

from .base import BaseCompressor
from ..exceptions import CompressorError


class LzmaCompressor(BaseCompressor):
    min_length = 100
    preset = 4

    def compress(self, value):
        if len(value) > self.min_length:
            return lzma.compress(value, preset=self.preset)
        return value

    def decompress(self, value):
        try:
            return lzma.decompress(value)
        except lzma.LZMAError as e:
            raise CompressorError(e)
