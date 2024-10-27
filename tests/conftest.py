import sys
from os import environ
from pathlib import Path
from typing import Iterable

import pytest
from xdist.scheduler import LoadScopeScheduling

from django_redis.cache import BaseCache
from tests.settings_wrapper import SettingsWrapper


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


@pytest.fixture()
def settings():
    """A Django settings object which restores changes after the testrun"""
    wrapper = SettingsWrapper()
    yield wrapper
    wrapper.finalize()


@pytest.fixture
def cache(cache_settings: str) -> Iterable[BaseCache]:
    from django import setup

    environ["DJANGO_SETTINGS_MODULE"] = f"settings.{cache_settings}"
    setup()

    from django.core.cache import cache as default_cache

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
