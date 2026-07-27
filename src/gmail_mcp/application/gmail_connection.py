from __future__ import annotations

from typing import Protocol

from gmail_mcp.domain.gmail_connection import ConnectionResult


class GmailConnectionPort(Protocol):
    def connect(self) -> ConnectionResult: ...

    def require_connection(self) -> ConnectionResult: ...

    def disconnect(self) -> ConnectionResult: ...


class ConnectGmailAccount:
    def __init__(self, connection: GmailConnectionPort) -> None:
        self._connection = connection

    def execute(self) -> ConnectionResult:
        return self._connection.connect()


class RequireGmailConnection:
    def __init__(self, connection: GmailConnectionPort) -> None:
        self._connection = connection

    def execute(self) -> ConnectionResult:
        return self._connection.require_connection()


class DisconnectGmailAccount:
    def __init__(self, connection: GmailConnectionPort) -> None:
        self._connection = connection

    def execute(self) -> ConnectionResult:
        return self._connection.disconnect()
