# -*- coding: utf-8 -*-

import sys

PY3 = sys.version_info[0] == 3

if PY3:
    text_type = str
else:
    text_type = unicode
