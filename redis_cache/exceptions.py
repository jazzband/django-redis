# -*- coding: utf-8 -*-

class ConnectionInterrumped(Exception):
    def __init__(self, connection):
        self.connection = connection
