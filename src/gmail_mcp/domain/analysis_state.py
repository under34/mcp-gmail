from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ThreadCandidate:
    """Thread-first metadata eligible for analysis; never contains mail body content."""

    account_fingerprint: str
    thread_id: str
    latest_message_id: str
    latest_message_at: str
    filter_hash: str


@dataclass(frozen=True)
class AnalysisRun:
    run_id: str
    account_fingerprint: str
    candidates: tuple[ThreadCandidate, ...]
    input_hash: str
    created_at: str
    covered_from: str | None
    covered_to: str | None
    status: str = "running"
    reason: str | None = None

    @classmethod
    def create(cls, account_fingerprint: str, candidates: list[ThreadCandidate]) -> AnalysisRun:
        snapshot = tuple(candidates)
        payload = [
            (
                candidate.thread_id,
                candidate.latest_message_id,
                candidate.latest_message_at,
                candidate.filter_hash,
            )
            for candidate in snapshot
        ]
        input_hash = hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
        timestamps = [candidate.latest_message_at for candidate in snapshot]
        return cls(
            str(uuid.uuid4()),
            account_fingerprint,
            snapshot,
            input_hash,
            datetime.now(UTC).isoformat(),
            min(timestamps, default=None),
            max(timestamps, default=None),
        )

    @classmethod
    def failed(cls, account_fingerprint: str, reason: str) -> AnalysisRun:
        return cls.create(account_fingerprint, []).finish("failed", reason)

    def finish(self, status: str, reason: str | None = None) -> AnalysisRun:
        if status not in {"complete", "partial", "failed"}:
            raise ValueError("Analysis run status must be complete, partial, or failed.")
        if status in {"partial", "failed"} and not (reason and reason.strip()):
            raise ValueError("Partial and failed analysis runs require a reason.")
        return AnalysisRun(
            self.run_id,
            self.account_fingerprint,
            self.candidates,
            self.input_hash,
            self.created_at,
            self.covered_from,
            self.covered_to,
            status,
            reason,
        )
