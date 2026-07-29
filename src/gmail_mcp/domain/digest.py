from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from gmail_mcp.domain.thread_summary import ThreadSummary

DigestStatus = Literal["complete", "partial", "failed"]
InclusionReason = Literal["new_message", "newly_matching", "reanalysis"]


@dataclass(frozen=True)
class DigestItem:
    summary: ThreadSummary
    inclusion_reason: InclusionReason

    @property
    def thread_id(self) -> str:
        return self.summary.thread_id


@dataclass(frozen=True)
class Digest:
    run_id: str
    account_fingerprint: str
    status: DigestStatus
    generated_at: str
    covered_from: str | None
    covered_to: str | None
    matching_thread_count: int
    items: tuple[DigestItem, ...]
    provider: str | None = None
    reason: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"complete", "partial", "failed"}:
            raise ValueError("Digest status is invalid.")
        if self.status in {"partial", "failed"} and not self.reason:
            raise ValueError("Incomplete digest requires a safe reason.")
        if self.status == "failed" and self.items:
            raise ValueError("Failed digest cannot contain items.")
        if self.matching_thread_count < len(self.items):
            raise ValueError("Digest item count exceeds matching thread count.")
