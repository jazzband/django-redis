from __future__ import annotations

import copy
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

import pytest
from django.core.cache import caches
from pytest import LogCaptureFixture
from redis.exceptions import ConnectionError as RedisConnectionError

from django_redis.client import ShardClient
from django_redis.exceptions import ConnectionInterrupted

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django_redis.cache import RedisCache


def make_key(key: str, prefix: str, version: str) -> str:
    return f"{prefix}#{version}#{key}"


def reverse_key(key: str) -> str:
    return key.split("#", 2)[2]


@pytest.fixture
def ignore_exceptions_cache(settings) -> RedisCache:
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    caches_setting["doesnotexist"]["OPTIONS"]["LOG_IGNORED_EXCEPTIONS"] = True
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
    settings.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
    return cast("RedisCache", caches["doesnotexist"])


def test_get_django_omit_exceptions_many_returns_default_arg(
    ignore_exceptions_cache: RedisCache,
):
    assert ignore_exceptions_cache._ignore_exceptions is True
    assert ignore_exceptions_cache.get_many(["key1", "key2", "key3"]) == {}


def test_get_django_omit_exceptions(
    caplog: LogCaptureFixture,
    ignore_exceptions_cache: RedisCache,
):
    assert ignore_exceptions_cache._ignore_exceptions is True
    assert ignore_exceptions_cache._log_ignored_exceptions is True

    assert ignore_exceptions_cache.get("key") is None
    assert ignore_exceptions_cache.get("key", "default") == "default"
    assert ignore_exceptions_cache.get("key", default="default") == "default"

    assert len(caplog.records) == 3
    assert all(
        record.levelname == "ERROR" and record.msg == "Exception ignored"
        for record in caplog.records
    )


def test_get_django_omit_exceptions_priority_1(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = False
    cache = cast("RedisCache", caches["doesnotexist"])
    assert cache._ignore_exceptions is True
    assert cache.get("key") is None


def test_get_django_omit_exceptions_priority_2(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = False
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_IGNORE_EXCEPTIONS = True
    cache = cast("RedisCache", caches["doesnotexist"])
    assert cache._ignore_exceptions is False
    with pytest.raises(RedisConnectionError):
        cache.get("key")


def reraise_exception(cache: RedisCache, exception: BaseException) -> None:
    raise exception


@pytest.fixture
def exception_handler() -> Mock:
    return Mock()


@pytest.fixture
def exception_handler_cache(settings, exception_handler: Mock) -> RedisCache:
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    caches_setting["doesnotexist"]["OPTIONS"]["EXCEPTION_HANDLER"] = exception_handler
    settings.CACHES = caches_setting
    return cast("RedisCache", caches["doesnotexist"])


def test_exception_handler_receives_the_original_exception(
    caplog: LogCaptureFixture,
    exception_handler: Mock,
    exception_handler_cache: RedisCache,
    settings,
):
    settings.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

    assert exception_handler_cache.get("key", "default") == "default"

    exception_handler.assert_called_once()
    cache, exception = exception_handler.call_args.args
    assert cache is exception_handler_cache
    assert isinstance(exception, RedisConnectionError)
    # The handler replaces the default "Exception ignored" log.
    assert caplog.records == []


def test_exception_handler_from_global_setting_as_dotted_path(settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    settings.CACHES = caches_setting
    settings.DJANGO_REDIS_EXCEPTION_HANDLER = "test_cache_options.reraise_exception"
    cache = cast("RedisCache", caches["doesnotexist"])

    with pytest.raises(RedisConnectionError) as excinfo:
        cache.get("key")

    # The re-raised error is not chained to the ConnectionInterrupted wrapper,
    # and its chain ends instead of looping back on itself.
    chain: list[BaseException] = []
    error: BaseException | None = excinfo.value
    while error is not None and error not in chain:
        chain.append(error)
        error = error.__cause__ or error.__context__
    assert error is None
    assert not any(isinstance(error, ConnectionInterrupted) for error in chain)


def test_exception_handler_option_takes_priority_over_global_setting(
    exception_handler: Mock,
    exception_handler_cache: RedisCache,
    settings,
):
    settings.DJANGO_REDIS_EXCEPTION_HANDLER = "test_cache_options.reraise_exception"

    assert exception_handler_cache.get("key") is None
    exception_handler.assert_called_once()


def test_exception_handler_is_not_called_when_exceptions_are_not_ignored(settings):
    exception_handler = Mock()
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["doesnotexist"]["OPTIONS"]["EXCEPTION_HANDLER"] = exception_handler
    settings.CACHES = caches_setting
    cache = cast("RedisCache", caches["doesnotexist"])

    with pytest.raises(RedisConnectionError):
        cache.get("key")
    exception_handler.assert_not_called()


@pytest.fixture
def key_prefix_cache(cache: RedisCache, settings) -> Iterable[RedisCache]:
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["default"]["KEY_PREFIX"] = "*"
    settings.CACHES = caches_setting
    yield cache


@pytest.fixture
def with_prefix_cache() -> Iterable[RedisCache]:
    with_prefix = cast("RedisCache", caches["with_prefix"])
    yield with_prefix
    with_prefix.clear()


class TestDjangoRedisCacheEscapePrefix:
    def test_delete_pattern(
        self,
        key_prefix_cache: RedisCache,
        with_prefix_cache: RedisCache,
    ):
        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        key_prefix_cache.delete_pattern("*")
        assert key_prefix_cache.has_key("a") is False
        assert with_prefix_cache.get("b") == "2"

    def test_iter_keys(
        self,
        key_prefix_cache: RedisCache,
        with_prefix_cache: RedisCache,
    ):
        if isinstance(key_prefix_cache.client, ShardClient):
            pytest.skip("ShardClient doesn't support iter_keys")

        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        assert list(key_prefix_cache.iter_keys("*")) == ["a"]

    def test_keys(self, key_prefix_cache: RedisCache, with_prefix_cache: RedisCache):
        key_prefix_cache.set("a", "1")
        with_prefix_cache.set("b", "2")
        keys = key_prefix_cache.keys("*")
        assert "a" in keys
        assert "b" not in keys


def test_custom_key_function(cache: RedisCache, settings):
    caches_setting = copy.deepcopy(settings.CACHES)
    caches_setting["default"]["KEY_FUNCTION"] = "test_cache_options.make_key"
    caches_setting["default"]["REVERSE_KEY_FUNCTION"] = "test_cache_options.reverse_key"
    settings.CACHES = caches_setting

    if isinstance(cache.client, ShardClient):
        pytest.skip("ShardClient doesn't support get_client")

    for key in ["foo-aa", "foo-ab", "foo-bb", "foo-bc"]:
        cache.set(key, "foo")

    res = cache.delete_pattern("*foo-a*")
    assert bool(res) is True

    keys = cache.keys("foo*")
    assert set(keys) == {"foo-bb", "foo-bc"}
    # ensure our custom function was actually called
    assert {k.decode() for k in cache.client.get_client(write=False).keys("*")} == (
        {"#1#foo-bc", "#1#foo-bb"}
    )
