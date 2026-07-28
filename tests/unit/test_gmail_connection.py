from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from gmail_mcp.application.gmail_connection import (
    ConnectGmailAccount,
    DisconnectGmailAccount,
    RequireGmailConnection,
)
from gmail_mcp.bootstrap import cli
from gmail_mcp.bootstrap.paths import get_app_paths
from gmail_mcp.bootstrap.settings import GmailSettings, ProviderStatus
from gmail_mcp.domain.gmail_connection import ConnectionResult


@dataclass
class FakeGmailConnection:
    connect_result: ConnectionResult
    require_result: ConnectionResult
    disconnect_calls: int = 0

    def connect(self) -> ConnectionResult:
        return self.connect_result

    def require_connection(self) -> ConnectionResult:
        return self.require_result

    def disconnect(self) -> ConnectionResult:
        self.disconnect_calls += 1
        return ConnectionResult.complete()


def test_connect_delegates_to_connection_port() -> None:
    connection = FakeGmailConnection(
        ConnectionResult.complete(email_address="owner@example.com"),
        ConnectionResult.complete(email_address="owner@example.com"),
    )

    result = ConnectGmailAccount(connection).execute()

    assert result.status == "complete"
    assert result.email_address == "owner@example.com"


def test_require_connection_surfaces_reconnect_action() -> None:
    connection = FakeGmailConnection(
        ConnectionResult.failed("Authorization is unavailable.", "Run connect-gmail."),
        ConnectionResult.failed("Authorization is unavailable.", "Run connect-gmail."),
    )

    result = RequireGmailConnection(connection).execute()

    assert result.status == "failed"
    assert result.next_action == "Run connect-gmail."


def test_disconnect_is_delegated_and_idempotent_at_port_boundary() -> None:
    connection = FakeGmailConnection(
        ConnectionResult.complete(),
        ConnectionResult.complete(),
    )

    DisconnectGmailAccount(connection).execute()
    DisconnectGmailAccount(connection).execute()

    assert connection.disconnect_calls == 2


def test_disconnect_cli_does_not_require_credentials_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    paths = get_app_paths(tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "load_gmail_settings",
        lambda **kwargs: GmailSettings(credentials_path=None, paths=paths),
    )
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "disconnect-gmail"])

    exit_code = cli.main()

    assert exit_code == 0
    assert capsys.readouterr().out == "complete\n"


def test_ai_provider_status_reports_selected_provider(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_provider_status", lambda: ProviderStatus("openai", True, False))
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "ai-provider-status"])

    assert cli.main() == 0
    assert "selected=openai" in capsys.readouterr().out


def test_filter_status_uses_account_identity_without_previewing_threads(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    paths = get_app_paths(tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "load_gmail_settings",
        lambda **kwargs: GmailSettings(credentials_path=None, paths=paths),
    )
    monkeypatch.setattr(
        cli.GmailOAuthAdapter, "current_account_email", lambda self: "owner@example.com"
    )
    monkeypatch.setattr(
        cli.GmailOAuthAdapter,
        "preview_threads",
        lambda self, query: (_ for _ in ()).throw(AssertionError("must not list threads")),
    )
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "gmail-filter-status"])

    assert cli.main() == 0
    assert "in:inbox" in capsys.readouterr().out


def test_set_filter_cli_requires_confirm_without_gmail_access(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    paths = get_app_paths(tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "load_gmail_settings",
        lambda **kwargs: GmailSettings(credentials_path=None, paths=paths),
    )
    monkeypatch.setattr(
        cli.GmailOAuthAdapter,
        "preview_threads",
        lambda self, query: (_ for _ in ()).throw(AssertionError("must not access Gmail")),
    )
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "set-gmail-filter", "--query", "in:inbox"])

    assert cli.main() == 1
    assert "--confirm" in capsys.readouterr().out
