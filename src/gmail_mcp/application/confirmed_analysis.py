from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol

from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.confirmation import (
    AnalysisConfirmation,
    AnalysisPreview,
    analysis_input_hash,
    filter_hash,
)
from gmail_mcp.domain.gmail_filter import GmailFilter
from gmail_mcp.domain.thread_summary import ThreadSummary

REFRESH_PREVIEW_ACTION = "Refresh the preview and confirm it again."
OPERATION = "summarize_gmail"


class ConfirmedGmailPort(Protocol):
    def current_account_email(self) -> str: ...

    def find_thread_candidates(
        self, account_fingerprint: str, query: str, filter_hash: str
    ) -> list[ThreadCandidate]: ...

    def fetch_clean_text(self, candidate: ThreadCandidate) -> str: ...


class ActiveFilterPort(Protocol):
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


class PlanAnalysisPort(Protocol):
    def execute(
        self,
        account_fingerprint: str,
        candidates: list[ThreadCandidate],
        *,
        reanalysis: bool,
        filter_hash: str,
    ) -> AnalysisRun: ...


class SummarizeRunPort(Protocol):
    def execute(
        self,
        run: AnalysisRun,
        *,
        texts: Mapping[str, str] | None = None,
        expected_provider: str | None = None,
    ) -> AnalysisRun: ...


class FinishRunPort(Protocol):
    def execute(
        self, run: AnalysisRun, status: str, *, reason: str | None = None
    ) -> AnalysisRun: ...


class SummariesPort(Protocol):
    def summaries_for_run(self, run_id: str) -> tuple[ThreadSummary, ...]: ...


class ConfirmedAdHocAnalysis:
    def __init__(
        self,
        gmail: ConfirmedGmailPort,
        filters: ActiveFilterPort,
        confirmations: ConfirmationPort,
        planner: PlanAnalysisPort,
        finish: FinishRunPort,
        summarize: SummarizeRunPort,
        summaries: SummariesPort,
        *,
        provider: str,
        now: Callable[[], datetime] | None = None,
        preview_ttl: timedelta = timedelta(minutes=5),
        confirmation_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._gmail = gmail
        self._filters = filters
        self._confirmations = confirmations
        self._planner = planner
        self._finish = finish
        self._summarize = summarize
        self._summaries = summaries
        self._provider = provider
        self._now = now or (lambda: datetime.now(UTC))
        self._preview_ttl = preview_ttl
        self._confirmation_ttl = confirmation_ttl

    def preview(self, query: str | None = None) -> dict[str, object]:
        try:
            email = self._gmail.current_account_email()
            account = _fingerprint(email)
            filter_ = (
                GmailFilter(query)
                if query is not None
                else self._filters.load(email) or GmailFilter.default()
            )
            current_filter_hash = filter_hash(filter_.query)
            candidates = tuple(
                self._gmail.find_thread_candidates(account, filter_.query, current_filter_hash)
            )
            if any(
                item.account_fingerprint != account or item.filter_hash != current_filter_hash
                for item in candidates
            ):
                raise ValueError("Gmail preview does not match the active account.")
            preview = AnalysisPreview(
                account,
                OPERATION,
                filter_.query,
                current_filter_hash,
                candidates,
                self._provider,
                self._now() + self._preview_ttl,
            )
            token = self._confirmations.save_preview(preview)
            return _complete(
                {
                    "phase": "preview",
                    "query": filter_.query,
                    "thread_ids": list(preview.ordered_thread_ids),
                    "thread_count": len(candidates),
                    "provider": self._provider,
                    "preview_token": token,
                }
            )
        except Exception:
            return _failed("Gmail analysis preview is unavailable.", "Reconnect Gmail and retry.")

    def confirm(self, preview_token: str) -> dict[str, object]:
        try:
            account = self._current_account()
            preview = self._confirmations.consume_preview(
                preview_token, account_fingerprint=account, now=self._now()
            )
            if (
                preview is None
                or preview.operation != OPERATION
                or preview.provider != self._provider
            ):
                return _failed(
                    "The analysis preview is invalid or expired.", REFRESH_PREVIEW_ACTION
                )
            lease = self._confirmations.acquire_execution_lease(account)
            if lease is None:
                return _failed("Gmail data deletion is in progress.", REFRESH_PREVIEW_ACTION)
            try:
                texts = self._fetch_snapshot(preview.candidates)
                if self._current_account() != account:
                    return _failed(
                        "Gmail account changed during confirmation.", REFRESH_PREVIEW_ACTION
                    )
                confirmation = AnalysisConfirmation(
                    account,
                    OPERATION,
                    preview.query,
                    preview.filter_hash,
                    preview.candidates,
                    self._provider,
                    analysis_input_hash(texts),
                    self._now() + self._confirmation_ttl,
                )
                token = self._confirmations.save_confirmation(confirmation)
            finally:
                self._confirmations.release_execution_lease(account, lease)
            return _complete(
                {
                    "phase": "confirmed",
                    "query": preview.query,
                    "thread_ids": list(preview.ordered_thread_ids),
                    "thread_count": len(preview.candidates),
                    "provider": self._provider,
                    "confirmation_token": token,
                }
            )
        except Exception:
            return _failed("The confirmed Gmail snapshot is unavailable.", REFRESH_PREVIEW_ACTION)

    def execute(self, confirmation_token: str | None) -> dict[str, object]:
        if not confirmation_token:
            return _failed("A valid confirmation token is required.", REFRESH_PREVIEW_ACTION)
        try:
            account = self._current_account()
            confirmation = self._confirmations.consume_confirmation(
                confirmation_token, account_fingerprint=account, now=self._now()
            )
            if (
                confirmation is None
                or confirmation.operation != OPERATION
                or confirmation.provider != self._provider
            ):
                return _failed(
                    "The confirmation token is invalid or expired.", REFRESH_PREVIEW_ACTION
                )
            lease = self._confirmations.acquire_execution_lease(account)
            if lease is None:
                return _failed("Gmail data deletion is in progress.", REFRESH_PREVIEW_ACTION)
            try:
                texts = self._fetch_snapshot(confirmation.candidates)
                if (
                    self._current_account() != account
                    or analysis_input_hash(texts) != confirmation.input_hash
                ):
                    return _failed(
                        "The confirmed Gmail input changed before analysis.", REFRESH_PREVIEW_ACTION
                    )

                run = self._planner.execute(
                    account,
                    list(confirmation.candidates),
                    reanalysis=True,
                    filter_hash=confirmation.filter_hash,
                )
                if run.candidates != confirmation.candidates:
                    if run.status == "running":
                        self._finish.execute(run, "failed", reason="Confirmed Gmail scope is busy.")
                    return _failed("Confirmed Gmail scope is unavailable.", REFRESH_PREVIEW_ACTION)
                if run.status == "running":
                    run = self._summarize.execute(
                        run,
                        texts={
                            candidate.thread_id: text
                            for candidate, text in zip(confirmation.candidates, texts, strict=True)
                        },
                        expected_provider=confirmation.provider,
                    )
                summaries = self._summaries.summaries_for_run(run.run_id)
                data = {
                    "thread_ids": list(
                        confirmation.candidates[i].thread_id
                        for i in range(len(confirmation.candidates))
                    ),
                    "provider": confirmation.provider,
                    "summaries": [_summary_data(summary) for summary in summaries],
                }
                if run.status == "complete":
                    return _complete(data)
                return {
                    "status": run.status,
                    "data": data if run.status == "partial" else None,
                    "reason": run.reason or "Gmail analysis could not be completed.",
                    "next_action": "Retry with a new confirmed preview.",
                }
            finally:
                self._confirmations.release_execution_lease(account, lease)
        except Exception:
            return _failed("The confirmed Gmail analysis is unavailable.", REFRESH_PREVIEW_ACTION)

    def _current_account(self) -> str:
        return _fingerprint(self._gmail.current_account_email())

    def _fetch_snapshot(self, candidates: tuple[ThreadCandidate, ...]) -> tuple[str, ...]:
        return tuple(self._gmail.fetch_clean_text(candidate) for candidate in candidates)


def _fingerprint(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _summary_data(summary: ThreadSummary) -> dict[str, object]:
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


def _complete(data: dict[str, object]) -> dict[str, object]:
    return {"status": "complete", "data": data, "reason": None, "next_action": None}


def _failed(reason: str, next_action: str) -> dict[str, object]:
    return {"status": "failed", "data": None, "reason": reason, "next_action": next_action}
