# -*- coding: utf-8 -*-

import warnings

from .default import DefaultClient
from .sharded import ShardClient
from .herd import HerdClient
from .experimental import SimpleFailoverClient


__all__ = ['DefaultClient', 'ShardClient',
           'HerdClient', 'SimpleFailoverClient',]

try:
    from .sentinel import SentinelClient
    __all__.append("SentinelClient")
except ImportError:
    warnings.warn("sentinel client is unsuported with redis-py<2.9",
                  RuntimeWarning)

