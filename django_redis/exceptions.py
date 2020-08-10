class ConnectionInterrupted(Exception):
    def __init__(self, connection, parent=None):
        self.connection = connection

    def __str__(self):
        error_type = type(self.__cause__).__name__
        error_msg = str(self.__cause__)
        return "Redis {}: {}".format(error_type, error_msg)


class CompressorError(Exception):
    pass
