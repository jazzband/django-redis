from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis


class ConnectionInterrupted(Exception):
    def __init__(self, connection: Redis | None) -> None:
        self.connection = connection

    def __str__(self) -> str:
        error_type = type(self.__cause__).__name__
        error_msg = str(self.__cause__)
        return f"Redis {error_type}: {error_msg}"


class CompressorError(Exception):
    pass
