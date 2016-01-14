# -*- coding: utf-8 -*-

class ConnectionInterrumped(Exception):
    """Deprecated exception name with a typo."""
    def __init__(self, connection, parent=None):
        self.connection = connection
        self.parent = parent


class ConnectionInterrupted(ConnectionInterrumped):
    def __str__(self):
      error_type = "ConnectionInterrupted"
      error_msg = "An error occurred while connecting to redis"

      if self.parent:
        error_type = self.parent.__class__.__name__
        error_msg = str(self.parent)

      return "Redis %s: %s" % (error_type, error_msg)


class CompressorError(Exception):
    pass
