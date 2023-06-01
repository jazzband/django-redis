from typing import Iterable

import pytest
from pytest_django.fixtures import SettingsWrapper
from django.core.cache import cache as default_cache

from django_redis.cache import BaseCache


@pytest.fixture(autouse=True)
def patch_settings(settings: SettingsWrapper):
    settings.CACHE_HERD_TIMEOUT = 2


@pytest.fixture
def cache() -> Iterable[BaseCache]:
    yield default_cache
    default_cache.clear()
