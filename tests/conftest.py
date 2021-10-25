from typing import Iterable

import pytest
from django.core.cache import cache as default_cache

from django_redis.cache import RedisCache


@pytest.fixture
def cache() -> Iterable[RedisCache]:
    yield default_cache
    default_cache.clear()
