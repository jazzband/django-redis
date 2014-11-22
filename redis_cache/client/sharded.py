from __future__ import absolute_import, unicode_literals
from django_redis.client.sharded import *
import warnings
warnings.warn("The 'redis_cache' package name is deprecated. Please rename it "
              "for 'django_redis'.", DeprecationWarning)
