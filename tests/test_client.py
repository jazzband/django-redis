import pytest
from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS, caches
from django.test import override_settings

from django_redis.client import DefaultClient, ShardClient


@pytest.fixture
def cache_client():
    client = caches[DEFAULT_CACHE_ALIAS].client
    client.set("TestClientClose", 0)
    yield client
    client.delete("TestClientClose")
    client.clear()


class TestClientClose:
    def test_close_client_disconnect_default(self, cache_client, mocker):
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert not mock.called

    def test_close_disconnect_settings(self, cache_client, settings, mocker):
        settings.DJANGO_REDIS_CLOSE_CONNECTION = True
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert mock.called

    def test_close_disconnect_settings_cache(self, cache_client, mocker):
        settings.CACHES[DEFAULT_CACHE_ALIAS]["OPTIONS"]["CLOSE_CONNECTION"] = True
        with override_settings(CACHES=settings.CACHES):
            # enabling override_settings context emits 'setting_changed' signal
            # (re-set the value to populate again client connections)
            cache_client.set("TestClientClose", 0)
            mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
            cache_client.close()
            assert mock.called

    def test_close_disconnect_client_options(self, cache_client, mocker):
        cache_client._options["CLOSE_CONNECTION"] = True
        mock = mocker.patch.object(cache_client.connection_factory, "disconnect")
        cache_client.close()
        assert mock.called


class TestDefaultClient:
    def test_delete_pattern_calls_get_client_given_no_client(self, mocker):
        get_client_mock = mocker.patch("test_client.DefaultClient.get_client")
        mocker.patch("test_client.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""

        client.delete_pattern(pattern="foo*")
        get_client_mock.assert_called_once_with(write=True)

    def test_delete_pattern_calls_make_pattern(self, mocker):
        make_pattern_mock = mocker.patch("test_client.DefaultClient.make_pattern")
        get_client_mock = mocker.patch(
            "test_client.DefaultClient.get_client", return_value=mocker.Mock()
        )
        mocker.patch("test_client.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*")

        kwargs = {"version": None, "prefix": None}
        # if not isinstance(caches['default'].client, ShardClient):
        # kwargs['prefix'] = None

        make_pattern_mock.assert_called_once_with("foo*", **kwargs)

    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(self, mocker):
        make_pattern_mock = mocker.patch("test_client.DefaultClient.make_pattern")
        get_client_mock = mocker.patch(
            "test_client.DefaultClient.get_client", return_value=mocker.Mock()
        )
        mocker.patch("test_client.DefaultClient.__init__", return_value=None)
        client = DefaultClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        get_client_mock.return_value.scan_iter.return_value = []

        client.delete_pattern(pattern="foo*", itersize=90210)

        get_client_mock.return_value.scan_iter.assert_called_once_with(
            count=90210, match=make_pattern_mock.return_value
        )


class TestShardClient:
    def test_delete_pattern_calls_scan_iter_with_count_if_itersize_given(self, mocker):
        mocker.patch("test_client.ShardClient.__init__", return_value=None)
        make_pattern_mock = mocker.patch("test_client.DefaultClient.make_pattern")
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""

        connection = mocker.Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*", itersize=10)

        connection.scan_iter.assert_called_once_with(
            count=10, match=make_pattern_mock.return_value
        )

    def test_delete_pattern_calls_scan_iter(self, mocker):
        make_pattern_mock = mocker.patch("test_client.DefaultClient.make_pattern")
        mocker.patch("test_client.ShardClient.__init__", return_value=None)
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        connection = mocker.Mock()
        connection.scan_iter.return_value = []
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.scan_iter.assert_called_once_with(
            match=make_pattern_mock.return_value
        )

    def test_delete_pattern_calls_delete_for_given_keys(self, mocker):
        mocker.patch("test_client.DefaultClient.make_pattern")
        mocker.patch("test_client.ShardClient.__init__", return_value=None)
        client = ShardClient()
        client._backend = mocker.Mock()
        client._backend.key_prefix = ""
        connection = mocker.Mock()
        connection.scan_iter.return_value = [mocker.Mock(), mocker.Mock()]
        connection.delete.return_value = 0
        client._serverdict = {"test": connection}

        client.delete_pattern(pattern="foo*")

        connection.delete.assert_called_once_with(*connection.scan_iter.return_value)
