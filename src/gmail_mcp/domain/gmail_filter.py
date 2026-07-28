from __future__ import annotations

from dataclasses import dataclass

DEFAULT_GMAIL_QUERY = "in:inbox -category:promotions -category:social"


@dataclass(frozen=True)
class GmailFilter:
    query: str

    def __post_init__(self) -> None:
        normalized = self.query.strip()
        if not normalized:
            raise ValueError("Gmail filter query must not be empty.")
        object.__setattr__(self, "query", normalized)

    @classmethod
    def default(cls) -> GmailFilter:
        return cls(DEFAULT_GMAIL_QUERY)


@dataclass(frozen=True)
class FilterPreview:
    filter: GmailFilter
    matching_thread_count: int
    account_email: str


@dataclass(frozen=True)
class FilterResult:
    status: str
    reason: str | None = None
    next_action: str | None = None
    filter: GmailFilter | None = None
    matching_thread_count: int | None = None
    account_email: str | None = None
    persisted: bool = False

    @classmethod
    def complete(cls, preview: FilterPreview, *, persisted: bool = False) -> FilterResult:
        return cls(
            "complete",
            filter=preview.filter,
            matching_thread_count=preview.matching_thread_count,
            account_email=preview.account_email,
            persisted=persisted,
        )

    @classmethod
    def failed(cls, reason: str, next_action: str) -> FilterResult:
        return cls("failed", reason=reason, next_action=next_action)
