from __future__ import annotations

import sys
from importlib import import_module
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from xdist.scheduler import LoadScopeScheduling

from tests.settings_wrapper import SettingsWrapper

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django_redis.cache import BaseCache


class FixtureScheduling(LoadScopeScheduling):
    """Split by [] value. This is very hackish and might blow up any time!"""

    def _split_scope(self, nodeid):
        if "[sqlite" in nodeid:
            return nodeid.rsplit("[")[-1].replace("]", "")
        return None


def pytest_xdist_make_scheduler(log, config):
    return FixtureScheduling(config, log)


def pytest_configure(config):
    sys.path.insert(0, str(Path(__file__).absolute().parent))
    # Django settings are initialized once per worker, not once per test.
    environ["DJANGO_SETTINGS_MODULE"] = "settings.sqlite"


@pytest.fixture()
def settings():
    """A Django settings object which restores changes after the testrun"""
    wrapper = SettingsWrapper()
    yield wrapper
    wrapper.finalize()


@pytest.fixture()
def cache(cache_settings: str) -> Iterable[BaseCache]:
    from django import setup
    from django.core.cache import cache as default_cache
    from django.test import override_settings

    setup()
    cache_module = import_module(f"settings.{cache_settings}")
    overrides = {
        "CACHES": cache_module.CACHES,
        "DJANGO_REDIS_CONNECTION_FACTORY": getattr(
            cache_module,
            "DJANGO_REDIS_CONNECTION_FACTORY",
            "django_redis.pool.ConnectionFactory",
        ),
    }
    if hasattr(cache_module, "CACHE_HERD_TIMEOUT"):
        overrides["CACHE_HERD_TIMEOUT"] = cache_module.CACHE_HERD_TIMEOUT

    # Switching DJANGO_SETTINGS_MODULE after django.setup() has no effect.
    # override_settings refreshes Django's cache handlers for each variant.
    with override_settings(**overrides):
        yield default_cache
        default_cache.clear()


def pytest_generate_tests(metafunc):
    if "cache" in metafunc.fixturenames or "session" in metafunc.fixturenames:
        # Mark
        settings = [
            "sqlite",
            "sqlite_gzip",
            "sqlite_herd",
            "sqlite_json",
            "sqlite_lz4",
            "sqlite_msgpack",
            "sqlite_sentinel",
            "sqlite_sentinel_opts",
            "sqlite_sharding",
            "sqlite_usock",
            "sqlite_zlib",
            "sqlite_zstd",
        ]
        metafunc.parametrize("cache_settings", settings)
