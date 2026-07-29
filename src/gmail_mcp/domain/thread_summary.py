from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Priority = Literal["wysoki", "średni", "niski"]
Provider = Literal["openai", "claude"]


@dataclass(frozen=True)
class ThreadSummary:
    account_fingerprint: str
    thread_id: str
    summary: str
    priority: Priority
    actions: tuple[str, ...]
    provider: Provider
    status: Literal["complete"] = "complete"
    schema_version: int = 1
    disclaimer: str = "Wynik AI może być niepełny lub błędny."

    def __post_init__(self) -> None:
        if not self.account_fingerprint.strip() or not self.thread_id.strip():
            raise ValueError("Summary source must identify an account and Gmail thread.")
        if self.schema_version != 1:
            raise ValueError("Only ThreadSummary schema version 1 is supported.")
        if self.status != "complete":
            raise ValueError("A stored ThreadSummary must have complete status.")
        if self.priority not in {"wysoki", "średni", "niski"}:
            raise ValueError("Priority must be wysoki, średni, or niski.")
        if self.provider not in {"openai", "claude"}:
            raise ValueError("Provider must be openai or claude.")
        if not self.summary.strip() or len(_sentences(self.summary)) > 3:
            raise ValueError("Summary must contain from one to three sentences.")
        if not isinstance(self.actions, tuple):
            raise ValueError("Actions must be an explicit tuple, including an empty tuple.")
        if any(not action.strip() for action in self.actions):
            raise ValueError("Actions must be non-empty when provided.")

    @property
    def source_link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#all/{self.thread_id}"


def _sentences(value: str) -> list[str]:
    return [part for part in re.split(r"[.!?]+", value.strip()) if part.strip()]
