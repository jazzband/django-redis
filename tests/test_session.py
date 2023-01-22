import base64
import unittest
from datetime import timedelta
from typing import Optional, Type

import django
import pytest
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.backends.cache import SessionStore as CacheSession
from django.core.cache import DEFAULT_CACHE_ALIAS, caches
from django.test import override_settings
from django.utils import timezone

from django_redis.serializers.msgpack import MSGPackSerializer

SessionType = Type[SessionBase]


# Copied from Django's sessions test suite. Keep in sync with upstream.
# https://github.com/django/django/blob/main/tests/sessions_tests/tests.py
class SessionTestsMixin:
    # This does not inherit from TestCase to avoid any tests being run with this
    # class, which wouldn't work, and to allow different TestCase subclasses to
    # be used.

    backend: Optional[SessionType] = None  # subclasses must specify

    def setUp(self):
        self.session = self.backend()

    def tearDown(self):
        # NB: be careful to delete any sessions created; stale sessions fill up
        # the /tmp (with some backends) and eventually overwhelm it after lots
        # of runs (think buildbots)
        self.session.delete()

    def test_new_session(self):
        self.assertIs(self.session.modified, False)
        self.assertIs(self.session.accessed, False)

    def test_get_empty(self):
        self.assertIsNone(self.session.get("cat"))

    def test_store(self):
        self.session["cat"] = "dog"
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.pop("cat"), "dog")

    def test_pop(self):
        self.session["some key"] = "exists"
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(self.session.pop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(self.session.get("some key"))

    def test_pop_default(self):
        self.assertEqual(
            self.session.pop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_default_named_argument(self):
        self.assertEqual(
            self.session.pop("some key", default="does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_no_default_keyerror_raised(self):
        with self.assertRaises(KeyError):
            self.session.pop("some key")

    def test_setdefault(self):
        self.assertEqual(self.session.setdefault("foo", "bar"), "bar")
        self.assertEqual(self.session.setdefault("foo", "baz"), "bar")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_update(self):
        self.session.update({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.get("update key"), 1)

    def test_has_key(self):
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn("some key", self.session)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_values(self):
        self.assertEqual(list(self.session.values()), [])
        self.assertIs(self.session.accessed, True)
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.values()), [1])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_keys(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_clear(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.session.clear()
        self.assertEqual(list(self.session.items()), [])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_save(self):
        self.session.save()
        self.assertIs(self.session.exists(self.session.session_key), True)

    def test_delete(self):
        self.session.save()
        self.session.delete(self.session.session_key)
        self.assertIs(self.session.exists(self.session.session_key), False)

    def test_flush(self):
        self.session["foo"] = "bar"
        self.session.save()
        prev_key = self.session.session_key
        self.session.flush()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertIsNone(self.session.session_key)
        self.assertIs(self.session.modified, True)
        self.assertIs(self.session.accessed, True)

    def test_cycle(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_key = self.session.session_key
        prev_data = list(self.session.items())
        self.session.cycle_key()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertEqual(list(self.session.items()), prev_data)

    def test_cycle_with_no_session_cache(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_data = self.session.items()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        self.session.cycle_key()
        self.assertCountEqual(self.session.items(), prev_data)

    def test_save_doesnt_clear_data(self):
        self.session["a"] = "b"
        self.session.save()
        self.assertEqual(self.session["a"], "b")

    def test_invalid_key(self):
        # Submitting an invalid session key (either by guessing, or if the db has
        # removed the key) results in a new key being generated.
        try:
            session = self.backend("1")
            session.save()
            self.assertNotEqual(session.session_key, "1")
            self.assertIsNone(session.get("cat"))
            session.delete()
        finally:
            # Some backends leave a stale cache entry for the invalid
            # session key; make sure that entry is manually deleted
            session.delete("1")

    def test_session_key_empty_string_invalid(self):
        """Falsey values (Such as an empty string) are rejected."""
        self.session._session_key = ""
        self.assertIsNone(self.session.session_key)

    def test_session_key_too_short_invalid(self):
        """Strings shorter than 8 characters are rejected."""
        self.session._session_key = "1234567"
        self.assertIsNone(self.session.session_key)

    def test_session_key_valid_string_saved(self):
        """Strings of length 8 and up are accepted and stored."""
        self.session._session_key = "12345678"
        self.assertEqual(self.session.session_key, "12345678")

    def test_session_key_is_read_only(self):
        def set_session_key(session):
            session.session_key = session._get_new_session_key()

        with self.assertRaises(AttributeError):
            set_session_key(self.session)

    # Custom session expiry
    def test_default_expiry(self):
        # A normal session has a max age equal to settings
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

        # So does a custom session with an idle expiration time of 0 (but it'll
        # expire at browser close)
        self.session.set_expiry(0)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_custom_expiry_seconds(self):
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
        modification = timezone.now()

        # Mock timezone.now, because set_expiry calls it on this code path.
        original_now = timezone.now
        try:
            timezone.now = lambda: modification
            self.session.set_expiry(timedelta(seconds=10))
        finally:
            timezone.now = original_now

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_datetime(self):
        modification = timezone.now()

        self.session.set_expiry(modification + timedelta(seconds=10))

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_reset(self):
        self.session.set_expiry(None)
        self.session.set_expiry(10)
        self.session.set_expiry(None)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_get_expire_at_browser_close(self):
        # Tests get_expire_at_browser_close with different settings and different
        # set_expiry calls
        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=False):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

    def test_decode(self):
        # Ensure we can decode what we encode
        data = {"a test key": "a test value"}
        encoded = self.session.encode(data)
        self.assertEqual(self.session.decode(encoded), data)

    def test_decode_failure_logged_to_security(self):
        bad_encode = base64.b64encode(b"flaskdj:alkdjf").decode("ascii")
        with self.assertLogs("django.security.SuspiciousSession", "WARNING") as cm:
            self.assertEqual({}, self.session.decode(bad_encode))
        # The failed decode is logged.
        self.assertIn("corrupted", cm.output[0])

    def test_actual_expiry(self):
        # this doesn't work with JSONSerializer (serializing timedelta)
        with override_settings(
            SESSION_SERIALIZER="django.contrib.sessions.serializers.PickleSerializer"
        ):
            self.session = self.backend()  # reinitialize after overriding settings

            # Regression test for #19200
            old_session_key = None
            new_session_key = None
            try:
                self.session["foo"] = "bar"
                self.session.set_expiry(-timedelta(seconds=10))
                self.session.save()
                old_session_key = self.session.session_key
                # With an expiry date in the past, the session expires instantly.
                new_session = self.backend(self.session.session_key)
                new_session_key = new_session.session_key
                self.assertNotIn("foo", new_session)
            finally:
                self.session.delete(old_session_key)
                self.session.delete(new_session_key)

    def test_session_load_does_not_create_record(self):
        """
        Loading an unknown session key does not create a session record.
        Creating session records on load is a DOS vulnerability.
        """
        session = self.backend("someunknownkey")
        session.load()

        self.assertIsNone(session.session_key)
        self.assertIs(session.exists(session.session_key), False)
        # provided unknown key was cycled, not reused
        self.assertNotEqual(session.session_key, "someunknownkey")

    def test_session_save_does_not_resurrect_session_logged_out_in_other_context(self):
        """
        Sessions shouldn't be resurrected by a concurrent request.
        """
        from django.contrib.sessions.backends.base import UpdateError

        # Create new session.
        s1 = self.backend()
        s1["test_data"] = "value1"
        s1.save(must_create=True)

        # Logout in another context.
        s2 = self.backend(s1.session_key)
        s2.delete()

        # Modify session in first context.
        s1["test_data"] = "value2"
        with self.assertRaises(UpdateError):
            # This should throw an exception as the session is deleted, not
            # resurrect the session.
            s1.save()

        self.assertEqual(s1.load(), {})


class SessionTests(SessionTestsMixin, unittest.TestCase):
    backend = CacheSession

    @pytest.mark.skipif(
        django.VERSION > (4, 2),
        reason="PickleSerializer is removed as of https://code.djangoproject.com/ticket/29708",
    )
    def test_actual_expiry(self):
        if isinstance(
            caches[DEFAULT_CACHE_ALIAS].client._serializer, MSGPackSerializer
        ):
            self.skipTest("msgpack serializer doesn't support datetime serialization")
        super().test_actual_expiry()
