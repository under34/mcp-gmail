from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from gmail_mcp.application.analysis_state import AnalysisStateError
from gmail_mcp.domain.gmail_connection import ConnectionResult
from gmail_mcp.domain.local_data import LocalDataResult


class LocalDataRepositoryPort(Protocol):
    def purge_expired_results(self, now: datetime) -> LocalDataResult: ...
    def begin_account_deletion(self, account_fingerprint: str) -> None: ...
    def delete_account_data(self, account_fingerprint: str) -> LocalDataResult: ...
    def renew_account_deletion(self, account_fingerprint: str) -> None: ...
    def end_account_deletion(self, account_fingerprint: str) -> None: ...


class TokenRemovalPort(Protocol):
    def disconnect(self) -> ConnectionResult: ...


class PurgeExpiredResults:
    def __init__(self, repository: LocalDataRepositoryPort) -> None:
        self._repository = repository

    def execute(self, *, now: datetime | None = None) -> LocalDataResult:
        instant = now or datetime.now(UTC)
        if instant.tzinfo is None:
            raise ValueError("Retention time must be timezone-aware.")
        try:
            return self._repository.purge_expired_results(instant.astimezone(UTC))
        except AnalysisStateError:
            return LocalDataResult(
                "failed", reason="Local retention is unavailable.", next_action="Retry later."
            )


class DeleteLocalData:
    def __init__(self, repository: LocalDataRepositoryPort, token: TokenRemovalPort) -> None:
        self._repository = repository
        self._token = token

    def execute(
        self, account_fingerprint: str | None, *, include_oauth_token: bool
    ) -> LocalDataResult:
        try:
            if account_fingerprint is None:
                result = LocalDataResult("complete")
            else:
                self._repository.begin_account_deletion(account_fingerprint)
                result = self._repository.delete_account_data(account_fingerprint)
        except AnalysisStateError:
            return LocalDataResult(
                "failed", reason="Local data deletion is unavailable.", next_action="Retry later."
            )
        try:
            if include_oauth_token:
                if account_fingerprint is not None:
                    self._repository.renew_account_deletion(account_fingerprint)
                token_result = self._token.disconnect()
                if token_result.status != "complete":
                    return LocalDataResult(
                        "partial",
                        result.deleted_digests,
                        result.deleted_summaries,
                        result.deleted_runs,
                        "Local results were removed, but OAuth token removal failed.",
                        "Reconnect Gmail only after resolving local token removal.",
                    )
            return result
        finally:
            try:
                if account_fingerprint is not None:
                    self._repository.end_account_deletion(account_fingerprint)
            except AnalysisStateError:
                pass
