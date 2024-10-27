import base64
from collections import Counter
from datetime import timedelta
from typing import Iterable

import pytest
from django.contrib.sessions.backends.cache import SessionStore as CacheSession
from django.test import override_settings
from django.utils import timezone


@pytest.fixture
def session(cache) -> Iterable[CacheSession]:
    s = CacheSession()

    yield s

    s.delete()


def test_new_session(session):
    assert session.modified is False
    assert session.accessed is False


def test_get_empty(session):
    assert session.get("cat") is None


def test_store(session):
    session["cat"] = "dog"
    assert session.modified is True
    assert session.pop("cat") == "dog"


def test_pop(session):
    session["some key"] = "exists"
    # Need to reset these to pretend we haven't accessed it:
    session.accessed = False
    session.modified = False

    assert session.pop("some key") == "exists"
    assert session.accessed is True
    assert session.modified is True
    assert session.get("some key") is None


def test_pop_default(session):
    assert session.pop("some key", "does not exist") == "does not exist"
    assert session.accessed is True
    assert session.modified is False


def test_pop_default_named_argument(session):
    assert session.pop("some key", default="does not exist") == "does not exist"
    assert session.accessed is True
    assert session.modified is False


def test_pop_no_default_keyerror_raised(session):
    with pytest.raises(KeyError):
        session.pop("some key")


def test_setdefault(session):
    assert session.setdefault("foo", "bar") == "bar"
    assert session.setdefault("foo", "baz") == "bar"
    assert session.accessed is True
    assert session.modified is True


def test_update(session):
    session.update({"update key": 1})
    assert session.accessed is True
    assert session.modified is True
    assert session.get("update key") == 1


def test_has_key(session):
    session["some key"] = 1
    session.modified = False
    session.accessed = False
    assert "some key" in session
    assert session.accessed is True
    assert session.modified is False


def test_values(session):
    assert list(session.values()) == []
    assert session.accessed is True
    session["some key"] = 1
    session.modified = False
    session.accessed = False
    assert list(session.values()) == [1]
    assert session.accessed is True
    assert session.modified is False


def test_keys(session):
    session["x"] = 1
    session.modified = False
    session.accessed = False
    assert list(session.keys()) == ["x"]
    assert session.accessed is True
    assert session.modified is False


def test_items(session):
    session["x"] = 1
    session.modified = False
    session.accessed = False
    assert list(session.items()) == [("x", 1)]
    assert session.accessed is True
    assert session.modified is False


def test_clear(session):
    session["x"] = 1
    session.modified = False
    session.accessed = False
    assert list(session.items()) == [("x", 1)]
    session.clear()
    assert list(session.items()) == []
    assert session.accessed is True
    assert session.modified is True


def test_save(session):
    session.save()
    assert session.exists(session.session_key) is True


def test_delete(session):
    session.save()
    session.delete(session.session_key)
    assert session.exists(session.session_key) is False


def test_flush(session):
    session["foo"] = "bar"
    session.save()
    prev_key = session.session_key
    session.flush()
    assert session.exists(prev_key) is False
    assert session.session_key != prev_key
    assert session.session_key is None
    assert session.modified is True
    assert session.accessed is True


def test_cycle(session):
    session["a"], session["b"] = "c", "d"
    session.save()
    prev_key = session.session_key
    prev_data = list(session.items())
    session.cycle_key()
    assert session.exists(prev_key) is False
    assert session.session_key != prev_key
    assert list(session.items()) == prev_data


def test_cycle_with_no_session_cache(session):
    session["a"], session["b"] = "c", "d"
    session.save()
    prev_data = session.items()
    session = CacheSession(session.session_key)
    assert hasattr(session, "_session_cache") is False
    session.cycle_key()
    assert Counter(session.items()) == Counter(prev_data)


def test_save_doesnt_clear_data(session):
    session["a"] = "b"
    session.save()
    assert session["a"] == "b"


def test_invalid_key(session):
    # Submitting an invalid session key (either by guessing, or if the db has
    # removed the key) results in a new key being generated.
    try:
        session = CacheSession("1")
        session.save()
        assert session.session_key != "1"
        assert session.get("cat") is None
        session.delete()
    finally:
        # Some backends leave a stale cache entry for the invalid
        # session key; make sure that entry is manually deleted
        session.delete("1")


def test_session_key_empty_string_invalid(session):
    """Falsey values (Such as an empty string) are rejected."""
    session._session_key = ""
    assert session.session_key is None


def test_session_key_too_short_invalid(session):
    """Strings shorter than 8 characters are rejected."""
    session._session_key = "1234567"
    assert session.session_key is None


def test_session_key_valid_string_saved(session):
    """Strings of length 8 and up are accepted and stored."""
    session._session_key = "12345678"
    assert session.session_key == "12345678"


def test_session_key_is_read_only(session):
    def set_session_key(s):
        s.session_key = s._get_new_session_key()

    with pytest.raises(AttributeError):
        set_session_key(session)


# Custom session expiry
def test_default_expiry(session, settings):
    # A normal session has a max age equal to settings
    assert session.get_expiry_age() == settings.SESSION_COOKIE_AGE

    # So does a custom session with an idle expiration time of 0 (but it'll
    # expire at browser close)
    session.set_expiry(0)
    assert session.get_expiry_age() == settings.SESSION_COOKIE_AGE


def test_custom_expiry_seconds(session):
    modification = timezone.now()

    session.set_expiry(10)

    date = session.get_expiry_date(modification=modification)
    assert date == modification + timedelta(seconds=10)

    age = session.get_expiry_age(modification=modification)
    assert age == 10


def test_custom_expiry_timedelta(session):
    modification = timezone.now()

    # Mock timezone.now, because set_expiry calls it on this code path.
    original_now = timezone.now
    try:
        timezone.now = lambda: modification
        session.set_expiry(timedelta(seconds=10))
    finally:
        timezone.now = original_now

    date = session.get_expiry_date(modification=modification)
    assert date == modification + timedelta(seconds=10)

    age = session.get_expiry_age(modification=modification)
    assert age == 10


def test_custom_expiry_datetime(session):
    modification = timezone.now()

    session.set_expiry(modification + timedelta(seconds=10))

    date = session.get_expiry_date(modification=modification)
    assert date == modification + timedelta(seconds=10)

    age = session.get_expiry_age(modification=modification)
    assert age == 10


def test_custom_expiry_reset(session, settings):
    session.set_expiry(None)
    session.set_expiry(10)
    session.set_expiry(None)
    assert session.get_expiry_age() == settings.SESSION_COOKIE_AGE


def test_get_expire_at_browser_close(session):
    # Tests get_expire_at_browser_close with different settings and different
    # set_expiry calls
    with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=False):
        session.set_expiry(10)
        assert session.get_expire_at_browser_close() is False

        session.set_expiry(0)
        assert session.get_expire_at_browser_close() is True

        session.set_expiry(None)
        assert session.get_expire_at_browser_close() is False

    with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
        session.set_expiry(10)
        assert session.get_expire_at_browser_close() is False

        session.set_expiry(0)
        assert session.get_expire_at_browser_close() is True

        session.set_expiry(None)
        assert session.get_expire_at_browser_close() is True


def test_decode(session):
    # Ensure we can decode what we encode
    data = {"a test key": "a test value"}
    encoded = session.encode(data)
    assert session.decode(encoded) == data


def test_decode_failure_logged_to_security(session, caplog):
    bad_encode = base64.b64encode(b"flaskdj:alkdjf").decode("ascii")
    # with self.assertLogs("django.security.SuspiciousSession", "WARNING") as cm:
    assert session.decode(bad_encode) == {}
    assert (
        "django.security.SuspiciousSession",
        30,
        "Session data corrupted",
    ) in caplog.record_tuples


def test_actual_expiry(session):
    # this doesn't work with JSONSerializer (serializing timedelta)
    with override_settings(
        SESSION_SERIALIZER="django.contrib.sessions.serializers.PickleSerializer"
    ):
        session = CacheSession()  # reinitialize after overriding settings

        # Regression test for #19200
        old_session_key = None
        new_session_key = None
        try:
            session["foo"] = "bar"
            session.set_expiry(-timedelta(seconds=10))
            session.save()
            old_session_key = session.session_key
            # With an expiry date in the past, the session expires instantly.
            new_session = CacheSession(session.session_key)
            new_session_key = new_session.session_key
            assert "foo" not in new_session
        finally:
            session.delete(old_session_key)
            session.delete(new_session_key)


def test_session_load_does_not_create_record(session):
    """
    Loading an unknown session key does not create a session record.
    Creating session records on load is a DOS vulnerability.
    """
    session = CacheSession("someunknownkey")
    session.load()

    assert session.session_key is None
    assert session.exists(session.session_key) is False
    # provided unknown key was cycled, not reused
    assert session.session_key != "someunknownkey"


def test_session_save_does_not_resurrect_session_logged_out_in_other_context(session):
    """
    Sessions shouldn't be resurrected by a concurrent request.
    """
    from django.contrib.sessions.backends.base import UpdateError

    # Create new session.
    s1 = CacheSession()
    s1["test_data"] = "value1"
    s1.save(must_create=True)

    # Logout in another context.
    s2 = CacheSession(s1.session_key)
    s2.delete()

    # Modify session in first context.
    s1["test_data"] = "value2"
    with pytest.raises(UpdateError):
        # This should throw an exception as the session is deleted, not
        # resurrect the session.
        s1.save()

    assert s1.load() == {}
