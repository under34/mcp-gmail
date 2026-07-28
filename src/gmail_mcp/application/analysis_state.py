from __future__ import annotations

import hashlib
import threading
from collections import defaultdict
from typing import Protocol

from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.gmail_filter import GmailFilter


class AnalysisStateError(RuntimeError):
    """Safe application-level failure while reading or writing local analysis state."""


class GmailCandidateError(ValueError):
    """Safe application-level failure while discovering Gmail thread metadata."""


class AnalysisStateRepositoryPort(Protocol):
    def plan(
        self,
        account_fingerprint: str,
        candidates: list[ThreadCandidate],
        *,
        reanalysis: bool = False,
        filter_hash: str,
    ) -> AnalysisRun: ...

    def finish(
        self,
        run: AnalysisRun,
        status: str,
        *,
        successful_thread_ids: set[str] | None = None,
        reason: str | None = None,
    ) -> AnalysisRun: ...


class PlanAnalysis:
    _locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def __init__(self, repository: AnalysisStateRepositoryPort) -> None:
        self._repository = repository

    def execute(
        self,
        account_fingerprint: str,
        candidates: list[ThreadCandidate],
        *,
        reanalysis: bool = False,
        filter_hash: str,
    ) -> AnalysisRun:
        try:
            self._validate_candidates(account_fingerprint, candidates)
            with self._locks[account_fingerprint]:
                return self._repository.plan(
                    account_fingerprint,
                    candidates,
                    reanalysis=reanalysis,
                    filter_hash=filter_hash,
                )
        except AnalysisStateError:
            return AnalysisRun.failed(account_fingerprint, "Local analysis state is unavailable.")

    @staticmethod
    def _validate_candidates(account_fingerprint: str, candidates: list[ThreadCandidate]) -> None:
        by_thread: dict[str, ThreadCandidate] = {}
        for candidate in candidates:
            if candidate.account_fingerprint != account_fingerprint:
                raise AnalysisStateError("Candidate account does not match analysis account.")
            existing = by_thread.setdefault(candidate.thread_id, candidate)
            if existing != candidate:
                raise AnalysisStateError("Conflicting candidates for one Gmail thread.")


class FinishAnalysis:
    def __init__(self, repository: AnalysisStateRepositoryPort) -> None:
        self._repository = repository

    def execute(
        self,
        run: AnalysisRun,
        status: str,
        *,
        successful_thread_ids: set[str] | None = None,
        reason: str | None = None,
    ) -> AnalysisRun:
        if status == "partial" and successful_thread_ids is None:
            status = "failed"
            reason = reason or "Partial analysis outcome is incomplete."
        try:
            with PlanAnalysis._locks[run.account_fingerprint]:
                return self._repository.finish(
                    run,
                    status,
                    successful_thread_ids=successful_thread_ids,
                    reason=reason,
                )
        except AnalysisStateError:
            return run.finish("failed", "Local analysis state is unavailable.")


class GmailCandidatePort(Protocol):
    def current_account_email(self) -> str: ...
    def find_thread_candidates(
        self, account_fingerprint: str, query: str, filter_hash: str
    ) -> list[ThreadCandidate]: ...


class ActiveFilterPort(Protocol):
    def load(self, account_email: str) -> GmailFilter | None: ...


class PlanActiveFilterAnalysis:
    def __init__(
        self,
        gmail: GmailCandidatePort,
        filters: ActiveFilterPort,
        state: AnalysisStateRepositoryPort,
    ) -> None:
        self._gmail = gmail
        self._filters = filters
        self._planner = PlanAnalysis(state)

    def execute(self, *, reanalysis: bool = False) -> AnalysisRun:
        try:
            email = self._gmail.current_account_email()
            account = hashlib.sha256(email.strip().lower().encode()).hexdigest()
            filter_ = self._filters.load(email) or GmailFilter.default()
            filter_hash = hashlib.sha256(filter_.query.encode()).hexdigest()
            candidates = self._gmail.find_thread_candidates(account, filter_.query, filter_hash)
            return self._planner.execute(
                account, candidates, reanalysis=reanalysis, filter_hash=filter_hash
            )
        except GmailCandidateError:
            return AnalysisRun.failed("", "Gmail candidate discovery is unavailable.")
