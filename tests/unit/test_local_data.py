from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from gmail_mcp.application.local_data import DeleteLocalData, PurgeExpiredResults
from gmail_mcp.domain.gmail_connection import ConnectionResult
from gmail_mcp.domain.local_data import LocalDataResult


@dataclass
class FakeRepository:
    result: LocalDataResult = LocalDataResult("complete")
    began: str | None = None
    ended: str | None = None

    def purge_expired_results(self, now: datetime) -> LocalDataResult:
        assert now.tzinfo is UTC
        return self.result

    def begin_account_deletion(self, account_fingerprint: str) -> None:
        self.began = account_fingerprint

    def delete_account_data(self, account_fingerprint: str) -> LocalDataResult:
        return self.result

    def renew_account_deletion(self, account_fingerprint: str) -> None:
        assert self.began == account_fingerprint

    def end_account_deletion(self, account_fingerprint: str) -> None:
        self.ended = account_fingerprint


@dataclass
class FakeToken:
    result: ConnectionResult
    calls: int = 0

    def disconnect(self) -> ConnectionResult:
        self.calls += 1
        return self.result


def test_retention_uses_an_injected_utc_clock() -> None:
    repository = FakeRepository(LocalDataResult("complete", 2, 3))

    result = PurgeExpiredResults(repository).execute(now=datetime(2026, 7, 29, tzinfo=UTC))

    assert result.deleted_digests == 2
    assert result.deleted_summaries == 3


def test_deletion_keeps_the_gate_until_optional_token_removal_finishes() -> None:
    repository = FakeRepository(LocalDataResult("complete", 2, 3, 1))
    token = FakeToken(ConnectionResult.failed("Token is unsafe.", "Remove it manually."))

    result = DeleteLocalData(repository, token).execute("account", include_oauth_token=True)

    assert result.status == "partial"
    assert token.calls == 1
    assert repository.began == repository.ended == "account"


def test_token_only_deletion_is_idempotent_without_an_account() -> None:
    repository = FakeRepository()
    token = FakeToken(ConnectionResult.complete())

    result = DeleteLocalData(repository, token).execute(None, include_oauth_token=True)

    assert result.status == "complete"
    assert token.calls == 1
    assert repository.began is None
