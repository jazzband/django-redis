from typing import Iterable

import pytest
from django.core.cache import cache as default_cache

from django_redis.cache import BaseCache


@pytest.fixture
def cache() -> Iterable[BaseCache]:
    yield default_cache
    default_cache.clear()
