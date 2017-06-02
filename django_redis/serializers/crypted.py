# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from .pickle import PickleSerializer

from cryptography.fernet import Fernet
from django.conf import settings

DEFAULT_KEY = r'kPEDO_pSrPh3qGJVfGAflLZXKAh4AuHU64tTlP-f_PY='


class CryptedSerializer(PickleSerializer):

    def __init__(self, *args, **kwargs):
        super(CryptedSerializer, self).__init__(*args, **kwargs)
        options = kwargs.get("options")
        default_key = options.get("SECRET", DEFAULT_KEY)
        key = default_key.encode("utf-8")
        self.crypter = Fernet(key)

    def dumps(self, value):
        val = super(CryptedSerializer, self).dumps(value)
        return self.crypter.encrypt(val)

    def loads(self, value):
        val = self.crypter.decrypt(value)
        return super(CryptedSerializer, self).loads(val)
