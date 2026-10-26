from __future__ import annotations

from importlib import import_module

from django.conf import settings


def test_cache_settings_follow_parametrization(cache, cache_settings: str) -> None:
    """Each cache variant must use its own configuration within a worker."""
    config = import_module(f"settings.{cache_settings}")

    assert settings.CACHES == config.CACHES
    assert cache._server == config.CACHES["default"]["LOCATION"]

    expected_factory = getattr(
        config,
        "DJANGO_REDIS_CONNECTION_FACTORY",
        "django_redis.pool.ConnectionFactory",
    )
    assert settings.DJANGO_REDIS_CONNECTION_FACTORY == expected_factory
