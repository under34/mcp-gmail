from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol

from gmail_mcp.domain.analysis_state import ThreadCandidate
from gmail_mcp.domain.confirmation import (
    AnalysisConfirmation,
    AnalysisPreview,
    analysis_input_hash,
    filter_hash,
)
from gmail_mcp.domain.gmail_filter import GmailFilter
from gmail_mcp.domain.thread_summary import ThreadSummary

OPERATION = "compare_summaries"
PROVIDERS = ("openai", "claude")
PROVIDER_SET = ",".join(PROVIDERS)
REFRESH = "Refresh the preview and confirm it again."


class GmailPort(Protocol):
    def current_account_email(self) -> str: ...
    def find_thread_candidates(
        self, account_fingerprint: str, query: str, filter_hash: str
    ) -> list[ThreadCandidate]: ...
    def fetch_clean_text(self, candidate: ThreadCandidate) -> str: ...


class FilterPort(Protocol):
    def load(self, account_email: str) -> GmailFilter | None: ...


class ConfirmationPort(Protocol):
    def save_preview(self, preview: AnalysisPreview) -> str: ...
    def consume_preview(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisPreview | None: ...
    def save_confirmation(self, confirmation: AnalysisConfirmation) -> str: ...
    def consume_confirmation(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisConfirmation | None: ...

    def acquire_execution_lease(self, account_fingerprint: str) -> str | None: ...

    def release_execution_lease(self, account_fingerprint: str, token: str) -> None: ...


class ProviderPort(Protocol):
    def summarize(
        self, *, account_fingerprint: str, thread_id: str, text: str
    ) -> ThreadSummary: ...


class ConfirmedComparison:
    def __init__(
        self,
        gmail: GmailPort,
        filters: FilterPort,
        confirmations: ConfirmationPort,
        providers: Mapping[str, ProviderPort],
        *,
        now: Callable[[], datetime] | None = None,
        ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._gmail, self._filters, self._confirmations, self._providers = (
            gmail,
            filters,
            confirmations,
            providers,
        )
        self._now, self._ttl = now or (lambda: datetime.now(UTC)), ttl

    def preview(self, thread_id: str | None) -> dict[str, object]:
        if not thread_id:
            return _failed(
                "A Gmail thread identifier is required.",
                "Choose a thread from the active Gmail filter.",
            )
        try:
            email = self._gmail.current_account_email()
            account = _fingerprint(email)
            filter_ = self._filters.load(email) or GmailFilter.default()
            current_hash = filter_hash(filter_.query)
            candidates = self._gmail.find_thread_candidates(account, filter_.query, current_hash)
            candidate = next((item for item in candidates if item.thread_id == thread_id), None)
            if (
                candidate is None
                or candidate.account_fingerprint != account
                or candidate.filter_hash != current_hash
            ):
                return _failed(
                    "The Gmail thread is outside the active filter.",
                    "Choose a thread from the active Gmail filter.",
                )
            preview = AnalysisPreview(
                account,
                OPERATION,
                filter_.query,
                current_hash,
                (candidate,),
                PROVIDER_SET,
                self._now() + self._ttl,
            )
            return _complete(
                {
                    "phase": "preview",
                    "thread_id": thread_id,
                    "query": filter_.query,
                    "providers": list(PROVIDERS),
                    "preview_token": self._confirmations.save_preview(preview),
                }
            )
        except Exception:
            return _failed("Gmail comparison preview is unavailable.", "Reconnect Gmail and retry.")

    def confirm(self, token: str) -> dict[str, object]:
        try:
            account = self._account()
            preview = self._confirmations.consume_preview(
                token, account_fingerprint=account, now=self._now()
            )
            if (
                preview is None
                or preview.operation != OPERATION
                or preview.provider != PROVIDER_SET
                or len(preview.candidates) != 1
            ):
                return _failed("The comparison preview is invalid or expired.", REFRESH)
            if not self._candidate_is_current(
                account, preview.candidates[0], preview.filter_hash
            ):
                return _failed("The Gmail thread is no longer in the active filter.", REFRESH)
            lease = self._confirmations.acquire_execution_lease(account)
            if lease is None:
                return _failed("Gmail data deletion is in progress.", REFRESH)
            try:
                text = self._gmail.fetch_clean_text(preview.candidates[0])
                if self._account() != account:
                    return _failed("Gmail account changed during confirmation.", REFRESH)
                confirmation = AnalysisConfirmation(
                    account, OPERATION, preview.query, preview.filter_hash, preview.candidates,
                    PROVIDER_SET, analysis_input_hash((text,)), self._now() + self._ttl,
                )
            finally:
                self._confirmations.release_execution_lease(account, lease)
            return _complete(
                {
                    "phase": "confirmed",
                    "thread_id": preview.candidates[0].thread_id,
                    "providers": list(PROVIDERS),
                    "confirmation_token": self._confirmations.save_confirmation(confirmation),
                }
            )
        except Exception:
            return _failed("The confirmed Gmail comparison is unavailable.", REFRESH)

    def execute(self, token: str | None) -> dict[str, object]:
        if not token:
            return _failed("A valid confirmation token is required.", REFRESH)
        try:
            account = self._account()
            confirmation = self._confirmations.consume_confirmation(
                token, account_fingerprint=account, now=self._now()
            )
            if (
                confirmation is None
                or confirmation.operation != OPERATION
                or confirmation.provider != PROVIDER_SET
                or len(confirmation.candidates) != 1
            ):
                return _failed("The comparison token is invalid or expired.", REFRESH)
            candidate = confirmation.candidates[0]
            if not self._candidate_is_current(
                account, candidate, confirmation.filter_hash
            ):
                return _failed("The Gmail thread is no longer in the active filter.", REFRESH)
            lease = self._confirmations.acquire_execution_lease(account)
            if lease is None:
                return _failed("Gmail data deletion is in progress.", REFRESH)
            try:
                text = self._gmail.fetch_clean_text(candidate)
                if (
                    self._account() != account
                    or analysis_input_hash((text,)) != confirmation.input_hash
                    or not self._candidate_is_current(account, candidate, confirmation.filter_hash)
                ):
                    return _failed("The confirmed Gmail input changed before comparison.", REFRESH)
                results = [
                    _provider_result(
                        name, self._providers.get(name), account, candidate.thread_id, text
                    )
                    for name in PROVIDERS
                ]
                succeeded = sum(result["status"] == "complete" for result in results)
                data = {
                    "thread_id": candidate.thread_id,
                    "providers": list(PROVIDERS),
                    "results": results,
                }
                if succeeded == 2:
                    return _complete(data)
                if succeeded == 1:
                    return {
                        "status": "partial",
                        "data": data,
                        "reason": "One provider could not complete the comparison.",
                        "next_action": (
                            "Review the provider error and retry with a new confirmation."
                        ),
                    }
                return {
                    "status": "failed",
                    "data": data,
                    "reason": "Neither provider could complete the comparison.",
                    "next_action": (
                        "Check provider configuration and retry with a new confirmation."
                    ),
                }
            finally:
                self._confirmations.release_execution_lease(account, lease)
        except Exception:
            return _failed("The confirmed Gmail comparison is unavailable.", REFRESH)

    def _account(self) -> str:
        return _fingerprint(self._gmail.current_account_email())

    def _candidate_is_current(
        self, account: str, candidate: ThreadCandidate, expected_hash: str
    ) -> bool:
        email = self._gmail.current_account_email()
        filter_ = self._filters.load(email) or GmailFilter.default()
        current_hash = filter_hash(filter_.query)
        if (
            _fingerprint(email) != account
            or candidate.account_fingerprint != account
            or current_hash != expected_hash
        ):
            return False
        return candidate in self._gmail.find_thread_candidates(account, filter_.query, current_hash)


def _provider_result(
    name: str, provider: ProviderPort | None, account: str, thread_id: str, text: str
) -> dict[str, object]:
    if provider is None:
        return {
            "provider": name,
            "status": "failed",
            "summary": None,
            "reason": "Provider is not configured.",
        }
    try:
        summary = provider.summarize(account_fingerprint=account, thread_id=thread_id, text=text)
    except Exception:
        return {
            "provider": name,
            "status": "failed",
            "summary": None,
            "reason": "Provider request failed.",
        }
    try:
        valid = (
            summary.provider == name
            and summary.account_fingerprint == account
            and summary.thread_id == thread_id
            and summary.schema_version == 1
        )
        result = _summary(summary) if valid else None
    except Exception:
        valid, result = False, None
    if not valid:
        return {
            "provider": name,
            "status": "failed",
            "summary": None,
            "reason": "Provider returned an invalid summary.",
        }
    return {
        "provider": name,
        "status": "complete",
        "summary": result,
        "reason": None,
    }


def _summary(summary: ThreadSummary) -> dict[str, object]:
    return {
        "thread_id": summary.thread_id,
        "source_link": summary.source_link,
        "summary": summary.summary,
        "priority": summary.priority,
        "actions": list(summary.actions),
        "provider": summary.provider,
        "status": summary.status,
        "schema_version": summary.schema_version,
        "disclaimer": summary.disclaimer,
    }


def _fingerprint(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _complete(data: dict[str, object]) -> dict[str, object]:
    return {"status": "complete", "data": data, "reason": None, "next_action": None}


def _failed(reason: str, action: str) -> dict[str, object]:
    return {"status": "failed", "data": None, "reason": reason, "next_action": action}
