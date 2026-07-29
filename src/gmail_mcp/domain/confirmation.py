from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from gmail_mcp.domain.analysis_state import ThreadCandidate


def filter_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def snapshot_hash(candidates: tuple[ThreadCandidate, ...]) -> str:
    payload = [
        [item.thread_id, item.latest_message_id, item.latest_message_at, item.filter_hash]
        for item in candidates
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def analysis_input_hash(texts: tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(list(texts), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class AnalysisPreview:
    account_fingerprint: str
    operation: str
    query: str
    filter_hash: str
    candidates: tuple[ThreadCandidate, ...]
    provider: str
    expires_at: datetime

    @property
    def ordered_thread_ids(self) -> tuple[str, ...]:
        return tuple(candidate.thread_id for candidate in self.candidates)

    @property
    def snapshot_hash(self) -> str:
        return snapshot_hash(self.candidates)


@dataclass(frozen=True)
class AnalysisConfirmation:
    account_fingerprint: str
    operation: str
    query: str
    filter_hash: str
    candidates: tuple[ThreadCandidate, ...]
    provider: str
    input_hash: str
    expires_at: datetime

    @property
    def snapshot_hash(self) -> str:
        return snapshot_hash(self.candidates)
