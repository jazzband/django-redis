# -*- coding: utf-8 -*-


class ConnectionInterrumped(Exception):
    """Deprecated exception name with a typo."""
    def __init__(self, connection, parent=None):
        self.connection = connection
        self.parent = parent


class ConnectionInterrupted(ConnectionInterrumped):
    pass
