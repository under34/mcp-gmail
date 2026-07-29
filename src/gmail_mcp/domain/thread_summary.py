from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Literal

Priority = Literal["wysoki", "średni", "niski"]
Provider = Literal["openai", "claude"]
AI_DISCLAIMER = "Wynik AI może być niepełny lub błędny."


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
    disclaimer: ClassVar[str] = AI_DISCLAIMER

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
        sentences = _sentences(self.summary)
        if not self.summary.strip() or not 1 <= len(sentences) <= 3:
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


def thread_summary_from_payload(
    payload: object, *, account_fingerprint: str, thread_id: str, provider: Provider
) -> ThreadSummary:
    if not isinstance(payload, dict) or set(payload) != {"summary", "priority", "actions"}:
        raise ValueError("Provider summary does not match schema version 1.")
    summary = payload["summary"]
    priority = payload["priority"]
    actions = payload["actions"]
    if not isinstance(summary, str) or not isinstance(priority, str):
        raise ValueError("Provider summary does not match schema version 1.")
    if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
        raise ValueError("Provider summary does not match schema version 1.")
    return ThreadSummary(
        account_fingerprint, thread_id, summary, priority, tuple(actions), provider
    )
