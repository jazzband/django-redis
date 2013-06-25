# -*- coding: utf-8 -*-


class ConnectionInterrumped(Exception):
    """Deprecated exception name with a typo."""
    def __init__(self, connection):
        self.connection = connection


class ConnectionInterrupted(ConnectionInterrumped):
    pass
