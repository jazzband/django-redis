from typing import Iterable, cast
from unittest.mock import Mock, patch

import pytest
from django.core.cache import DEFAULT_CACHE_ALIAS, caches
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from django_redis.cache import RedisCache
from django_redis.client import DefaultClient, ShardClient


@pytest.fixture
def cache_client() -> Iterable[DefaultClient]:
    client = cast(RedisCache, caches[DEFAULT_CACHE_ALIAS]).client
    client.set("TestClientClose", 0)
    yield client
    client.delete("TestClientClose")
    client.clear()


class TestClientClose:
    def test_close_client_disconnect_default(
        self, cache_client: DefaultClient, mocker: MockerFixture
    ):
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert not mock.called

    def test_close_disconnect_settings(
        self,
        cache_client: DefaultClient,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ):
        settings.DJANGO_REDIS_CLOSE_CONNECTION = True
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert mock.called

    def test_close_disconnect_settings_cache(
        self,
        cache_client: DefaultClient,
        mocker: MockerFixture,
        settings: SettingsWrapper,
    ):
        settings.CACHES[DEFAULT_CACHE_ALIAS]["OPTIONS"]["CLOSE_CONNECTION"] = True
        cache_client.set("TestClientClose", 0)
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert mock.called

    def test_close_disconnect_client_options(
        self, cache_client: DefaultClient, mocker: MockerFixture
    ):
        cache_client._options["CLOSE_CONNECTION"] = True
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert mock.called


class TestDefaultClient:
    @patch("test_client.DefaultClient.get_client")
    @patch("test_client.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_get_client_given_no_client(
        self, init_mock, get_client_mock
    ):
        client = DefaultClient()  # type: ignore
        client._backend = Mock()
        client._backend.key_prefix = ""

        client.delete_pattern(pattern="foo*")
        get_client_mock.assert_called_once_with(write=True)

    @patch("test_client.DefaultClient.make_pattern")
    @patch("test_client.DefaultClient.get_client", return_value=Mock())
    @patch("test_client.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_make_pattern(
        self, init_mock, get_client_mock, make_pattern_mock
    ):
        client = DefaultClient()  # type: ignore
        client._backend = Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*")

        kwargs = {"version": None, "prefix": None}
        # if not isinstance(caches['default'].client, ShardClient):
        # kwargs['prefix'] = None

        make_pattern_mock.assert_called_once_with("foo*", **kwargs)

    @patch("test_client.DefaultClient.make_pattern")
    @patch("test_client.DefaultClient.get_client", return_value=Mock())
    @patch("test_client.DefaultClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
        self, init_mock, get_client_mock, make_pattern_mock
    ):
        client = DefaultClient()  # type: ignore
        client._backend = Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*", itersize=90210)

        get_client_mock.return_value.scan_iter.assert_called_once_with(
            count=90210, match=make_pattern_mock.return_value
        )


class TestShardClient:
    @patch("test_client.DefaultClient.make_pattern")
    @patch("test_client.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(
        self, init_mock, make_pattern_mock
    ):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""

        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*", itersize=10)

        connection.scan_iter.assert_called_once_with(
            count=10, match=make_pattern_mock.return_value
        )

    @patch("test_client.DefaultClient.make_pattern")
    @patch("test_client.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_scan_iter(self, init_mock, make_pattern_mock):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        connection = Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.scan_iter.assert_called_once_with(
            match=make_pattern_mock.return_value
        )

    @patch("test_client.DefaultClient.make_pattern")
    @patch("test_client.ShardClient.__init__", return_value=None)
    def test_delete_pattern_calls_delete_for_given_keys(
        self, init_mock, make_pattern_mock
    ):
        client = ShardClient()
        client._backend = Mock()
        client._backend.key_prefix = ""
        connection = Mock()
        connection.scan_iter.return_value = [Mock(), Mock()]
        connection.delete.return_value = 0
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.delete.assert_called_once_with(*connection.scan_iter.return_value)
