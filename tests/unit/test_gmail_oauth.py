from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

from gmail_mcp.adapters import gmail_oauth
from gmail_mcp.adapters.gmail_oauth import GMAIL_SCOPES, GmailOAuthAdapter
from gmail_mcp.domain.gmail_connection import ConnectionResult


class FakeCredentials:
    def __init__(
        self, *, valid: bool, expired: bool = False, refresh_token: str | None = None
    ) -> None:
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refreshed = False

    def refresh(self, request: object) -> None:
        self.refreshed = True
        self.valid = True

    def to_json(self) -> str:
        return "{\"refresh_token\":\"fake\"}"


def _profile_build(*args: object, **kwargs: object) -> object:
    class Request:
        def execute(self) -> dict[str, str]:
            return {"emailAddress": "owner@example.com"}

    class Users:
        def getProfile(self, *, userId: str) -> Request:
            assert userId == "me"
            return Request()

    class Service:
        def users(self) -> Users:
            return Users()

    return Service()


def test_connect_uses_only_readonly_scope_and_saves_token(
    tmp_path: Path, monkeypatch
) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")
    token_path = tmp_path / "app-data" / "oauth" / "token.json"
    credentials = FakeCredentials(valid=True)
    captured: dict[str, object] = {}

    class Flow:
        def run_local_server(self, **kwargs: object) -> FakeCredentials:
            captured.update(kwargs)
            return credentials

    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: captured.update(path=path, scopes=scopes) or Flow(),
    )
    monkeypatch.setattr(gmail_oauth, "build", _profile_build)

    result = GmailOAuthAdapter(credentials_path, token_path).connect()

    assert result.email_address == "owner@example.com"
    assert captured["scopes"] == GMAIL_SCOPES
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 0
    assert token_path.is_file()


def test_expired_token_refreshes_without_browser(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials(valid=False, expired=True, refresh_token="refresh")
    monkeypatch.setattr(
        gmail_oauth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(gmail_oauth, "build", _profile_build)
    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda *args: (_ for _ in ()).throw(AssertionError("browser flow should not run")),
    )

    result = GmailOAuthAdapter(tmp_path / "credentials.json", token_path).connect()

    assert result.status == "complete"
    assert credentials.refreshed is True


def test_authorization_failure_returns_reconnect_action(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda *args: (_ for _ in ()).throw(RuntimeError("revoked")),
    )

    result = GmailOAuthAdapter(tmp_path / "credentials.json", tmp_path / "token.json").connect()

    assert result.status == "failed"
    assert result.next_action == "Run gmail-mcp connect-gmail."


def test_disconnect_and_status_reject_token_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    token_path = tmp_path / "token.json"
    token_path.symlink_to(target)
    adapter = GmailOAuthAdapter(tmp_path / "credentials.json", token_path)

    assert adapter.require_connection().status == "failed"
    assert adapter.disconnect().status == "failed"


def test_status_with_unrefreshable_token_never_starts_browser(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials(valid=False)
    monkeypatch.setattr(
        gmail_oauth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda *args: (_ for _ in ()).throw(AssertionError("browser flow must not run")),
    )

    result = GmailOAuthAdapter(tmp_path / "credentials.json", token_path).require_connection()

    assert result.status == "failed"
    assert result.next_action == "Run gmail-mcp connect-gmail."


def test_failed_refresh_removes_bad_token_for_a_later_explicit_reconnect(
    tmp_path: Path, monkeypatch
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials(valid=False, expired=True, refresh_token="refresh")
    monkeypatch.setattr(
        gmail_oauth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(
        credentials,
        "refresh",
        lambda request: (_ for _ in ()).throw(RuntimeError("revoked")),
    )

    result = GmailOAuthAdapter(tmp_path / "credentials.json", token_path).connect()

    assert result.status == "failed"
    assert not token_path.exists()


def test_token_is_written_with_private_permissions_on_posix(tmp_path: Path, monkeypatch) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")
    token_path = tmp_path / "token.json"
    class Flow:
        def run_local_server(self, **kwargs: object) -> FakeCredentials:
            return FakeCredentials(valid=True)

    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow, "from_client_secrets_file", lambda *args: Flow()
    )
    monkeypatch.setattr(gmail_oauth, "build", _profile_build)

    GmailOAuthAdapter(credentials_path, token_path).connect()

    if os.name == "posix":
        assert token_path.stat().st_mode & 0o777 == 0o600


def test_disconnect_returns_failed_for_an_unsafe_directory(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.mkdir()

    result = GmailOAuthAdapter(None, token_path).disconnect()

    assert result.status == "failed"


def test_corrupt_token_starts_explicit_oauth_flow(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("not-json", encoding="utf-8")
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        gmail_oauth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: (_ for _ in ()).throw(ValueError("corrupt token")),
    )

    class Flow:
        def run_local_server(self, **kwargs: object) -> FakeCredentials:
            return FakeCredentials(valid=True)

    monkeypatch.setattr(
        gmail_oauth.InstalledAppFlow, "from_client_secrets_file", lambda *args: Flow()
    )
    monkeypatch.setattr(gmail_oauth, "build", _profile_build)

    result = GmailOAuthAdapter(credentials_path, token_path).connect()

    assert result.status == "complete"


def test_server_revoked_token_is_removed_for_reconnect(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials(valid=True)
    monkeypatch.setattr(
        gmail_oauth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )

    class Response:
        status = 401
        reason = "Unauthorized"

    monkeypatch.setattr(
        GmailOAuthAdapter,
        "_profile_email",
        lambda self, credentials: (_ for _ in ()).throw(HttpError(Response(), b"revoked")),
    )

    result = GmailOAuthAdapter(tmp_path / "credentials.json", token_path).connect()

    assert result.status == "failed"
    assert not token_path.exists()


def test_preview_threads_counts_all_pages(tmp_path: Path, monkeypatch) -> None:
    adapter = GmailOAuthAdapter(None, tmp_path / "token.json")
    monkeypatch.setattr(
        adapter, "require_connection", lambda: ConnectionResult.complete("owner@example.com")
    )
    monkeypatch.setattr(adapter, "_load_credentials", lambda: object())

    class Request:
        def __init__(self, response: dict[str, object]) -> None:
            self._response = response

        def execute(self) -> dict[str, object]:
            return self._response

    class Threads:
        def list(self, **kwargs: object) -> Request:
            if kwargs["pageToken"] is None:
                return Request({"threads": [{"id": "one"}], "nextPageToken": "next"})
            return Request({"threads": [{"id": "two"}, {"id": "three"}]})

    class Users:
        def threads(self) -> Threads:
            return Threads()

    class Service:
        def users(self) -> Users:
            return Users()

    monkeypatch.setattr(gmail_oauth, "build", lambda *args, **kwargs: Service())

    assert adapter.preview_threads("in:inbox") == ("owner@example.com", 3)


def test_preview_threads_rejects_repeated_page_token(tmp_path: Path, monkeypatch) -> None:
    adapter = GmailOAuthAdapter(None, tmp_path / "token.json")
    monkeypatch.setattr(
        adapter, "require_connection", lambda: ConnectionResult.complete("owner@example.com")
    )
    monkeypatch.setattr(adapter, "_load_credentials", lambda: object())

    class Request:
        def execute(self) -> dict[str, object]:
            return {"threads": [], "nextPageToken": "again"}

    class Threads:
        def list(self, **kwargs: object) -> Request:
            return Request()

    class Users:
        def threads(self) -> Threads:
            return Threads()

    class Service:
        def users(self) -> Users:
            return Users()

    monkeypatch.setattr(gmail_oauth, "build", lambda *args, **kwargs: Service())

    with pytest.raises(ValueError, match="pagination"):
        adapter.preview_threads("in:inbox")


def test_find_thread_candidates_uses_thread_metadata_not_message_bodies(
    tmp_path: Path, monkeypatch
) -> None:
    adapter = GmailOAuthAdapter(None, tmp_path / "token.json")
    monkeypatch.setattr(
        adapter, "require_connection", lambda: ConnectionResult.complete("owner@example.com")
    )
    monkeypatch.setattr(adapter, "_load_credentials", lambda: object())
    captured: dict[str, object] = {}

    class Request:
        def __init__(self, response: dict[str, object]) -> None:
            self._response = response

        def execute(self) -> dict[str, object]:
            return self._response

    class Threads:
        def list(self, **kwargs: object) -> Request:
            captured["query"] = kwargs["q"]
            return Request({"threads": [{"id": "thread-1"}]})

        def get(self, **kwargs: object) -> Request:
            assert kwargs == {"userId": "me", "id": "thread-1", "format": "metadata"}
            return Request(
                {
                    "messages": [
                        {"id": "old", "internalDate": "0"},
                        {"id": "latest", "internalDate": "1722124800000"},
                    ]
                }
            )

    class Users:
        def threads(self) -> Threads:
            return Threads()

    class Service:
        def users(self) -> Users:
            return Users()

    monkeypatch.setattr(gmail_oauth, "build", lambda *args, **kwargs: Service())

    account = hashlib.sha256(b"owner@example.com").hexdigest()
    candidates = adapter.find_thread_candidates(account, "label:work", "filter-hash")

    assert captured["query"] == "label:work"
    assert [(item.thread_id, item.latest_message_id) for item in candidates] == [
        ("thread-1", "latest")
    ]
