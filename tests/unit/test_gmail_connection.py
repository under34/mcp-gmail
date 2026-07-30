from __future__ import annotations

import os
import subprocess
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
from gmail_mcp.bootstrap.settings import GmailSettings, ProviderStatus, Settings
from gmail_mcp.domain.digest import Digest
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


def test_daily_digest_cli_uses_the_composed_runner(tmp_path: Path, monkeypatch, capsys) -> None:
    paths = get_app_paths(tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings("openai", "key", None, None, paths),
    )

    class FakeRunner:
        def __init__(self, *args: object) -> None:
            pass

        def execute(self) -> Digest:
            return Digest("run", "account", "complete", "now", None, None, 0, ())

    monkeypatch.setattr(cli, "RunDailyDigest", FakeRunner)
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "run-daily-digest"])

    assert cli.main() == 0
    assert "complete: threads=0" in capsys.readouterr().out


def test_daily_digest_cli_reports_a_persisted_failed_digest(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    paths = get_app_paths(tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings("claude", None, "key", None, paths),
    )

    class FakeRunner:
        def __init__(self, *args: object) -> None:
            pass

        def execute(self) -> Digest:
            return Digest(
                "run", "account", "failed", "now", None, None, 2, (), "claude",
                "The selected AI provider is unavailable. Check credentials or billing.",
                "Check credentials or billing and retry.",
            )

    monkeypatch.setattr(cli, "RunDailyDigest", FakeRunner)
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "run-daily-digest"])

    assert cli.main() == 1
    output = capsys.readouterr().out
    assert output == (
        "failed: threads=2 The selected AI provider is unavailable. "
        "Check credentials or billing.\n"
    )


def test_daily_digest_entry_point_reports_disabled_schedule_without_external_calls(
    tmp_path: Path,
) -> None:
    environment = {
        **os.environ,
        "AI_PROVIDER": "claude",
        "ANTHROPIC_API_KEY": "test-key",
        "DIGEST_SCHEDULE_ENABLED": "false",
        "GMAIL_MCP_DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [str(Path(sys.executable).with_name("gmail-mcp")), "run-daily-digest", "--scheduled"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "complete: digest schedule is disabled\n"
    assert result.stderr == ""


def test_delete_local_data_cli_requires_confirmation_before_loading_settings(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "load_gmail_settings",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not load settings")),
    )
    monkeypatch.setattr(sys, "argv", ["gmail-mcp", "delete-local-data"])

    assert cli.main() == 1
    assert "--confirm" in capsys.readouterr().out


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
