from __future__ import annotations

from copy import deepcopy
from importlib import import_module

from django.conf import settings


def test_cache_settings_follow_parametrization(cache, cache_settings: str) -> None:
    """Each cache variant must use its own configuration within a worker."""
    config = import_module(f"settings.{cache_settings}")

    expected_caches = deepcopy(config.CACHES)
    if cache_settings in {"sqlite_sentinel", "sqlite_sentinel_opts"}:
        expected_caches["default"]["OPTIONS"]["CONNECTION_POOL_CLASS"] = (
            "redis.sentinel.SentinelConnectionPool"
        )

    assert expected_caches == settings.CACHES
    assert cache._server == config.CACHES["default"]["LOCATION"]

    expected_factory = getattr(
        config,
        "DJANGO_REDIS_CONNECTION_FACTORY",
        "django_redis.pool.ConnectionFactory",
    )
    assert expected_factory == settings.DJANGO_REDIS_CONNECTION_FACTORY
