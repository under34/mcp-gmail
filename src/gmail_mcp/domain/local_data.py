from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LocalDataStatus = Literal["complete", "partial", "failed"]


@dataclass(frozen=True)
class LocalDataResult:
    status: LocalDataStatus
    deleted_digests: int = 0
    deleted_summaries: int = 0
    deleted_runs: int = 0
    reason: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if min(self.deleted_digests, self.deleted_summaries, self.deleted_runs) < 0:
            raise ValueError("Deletion counts cannot be negative.")
        if self.status == "complete" and (self.reason or self.next_action):
            raise ValueError("A complete deletion result has no recovery details.")
        if self.status != "complete" and (not self.reason or not self.next_action):
            raise ValueError("An incomplete deletion result requires recovery details.")
