from __future__ import annotations

from dataclasses import dataclass, field

from gmail_mcp.application.gmail_filter import PreviewGmailFilter, SaveActiveGmailFilter
from gmail_mcp.domain.gmail_filter import GmailFilter


@dataclass
class FakeGmail:
    calls: list[str] = field(default_factory=list)
    failure: Exception | None = None

    def preview_threads(self, query: str) -> tuple[str, int]:
        self.calls.append(query)
        if self.failure:
            raise self.failure
        return "owner@example.com", 3


@dataclass
class FakeRepository:
    saved: list[tuple[str, GmailFilter]] = field(default_factory=list)

    def load(self, account_email: str) -> GmailFilter | None:
        return None

    def save(self, account_email: str, filter_: GmailFilter) -> None:
        self.saved.append((account_email, filter_))


def test_preview_returns_thread_count_and_normalized_query() -> None:
    gmail = FakeGmail()

    result = PreviewGmailFilter(gmail).execute("  from:boss  ")

    assert result.status == "complete"
    assert result.filter == GmailFilter("from:boss")
    assert result.matching_thread_count == 3
    assert gmail.calls == ["from:boss"]


def test_save_requires_confirm_without_gmail_call() -> None:
    gmail = FakeGmail()
    repository = FakeRepository()

    result = SaveActiveGmailFilter(PreviewGmailFilter(gmail), repository).execute(
        "in:inbox", confirmed=False
    )

    assert result.status == "failed"
    assert gmail.calls == []
    assert repository.saved == []


def test_confirmed_save_uses_one_preview_and_persists_current_account() -> None:
    gmail = FakeGmail()
    repository = FakeRepository()

    result = SaveActiveGmailFilter(PreviewGmailFilter(gmail), repository).execute(
        "label:work", confirmed=True
    )

    assert result.status == "complete"
    assert result.persisted is True
    assert gmail.calls == ["label:work"]
    assert repository.saved == [("owner@example.com", GmailFilter("label:work"))]


def test_preview_failure_never_persists_filter() -> None:
    gmail = FakeGmail(failure=RuntimeError("oauth"))
    repository = FakeRepository()

    result = SaveActiveGmailFilter(PreviewGmailFilter(gmail), repository).execute(
        "in:inbox", confirmed=True
    )

    assert result.status == "failed"
    assert repository.saved == []
