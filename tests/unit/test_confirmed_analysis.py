from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from gmail_mcp.application.confirmed_analysis import ConfirmedAdHocAnalysis
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.confirmation import AnalysisConfirmation, AnalysisPreview
from gmail_mcp.domain.gmail_filter import GmailFilter
from gmail_mcp.domain.thread_summary import ThreadSummary


def _candidate(account: str, thread_id: str, message_id: str) -> ThreadCandidate:
    return ThreadCandidate(account, thread_id, message_id, "2026-07-29T08:00:00+00:00", "filter")


@dataclass
class FakeGmail:
    email: str = "owner@example.com"
    candidates: list[ThreadCandidate] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    text_calls: int = 0

    def current_account_email(self) -> str:
        return self.email

    def find_thread_candidates(
        self, account: str, query: str, filter_hash: str
    ) -> list[ThreadCandidate]:
        return [
            ThreadCandidate(
                account, item.thread_id, item.latest_message_id, item.latest_message_at, filter_hash
            )
            for item in self.candidates
        ]

    def fetch_clean_text(self, candidate: ThreadCandidate) -> str:
        self.text_calls += 1
        return self.texts[candidate.thread_id]


@dataclass
class FakeFilters:
    filter_: GmailFilter | None = GmailFilter("label:work")
    saves: int = 0

    def load(self, account_email: str) -> GmailFilter | None:
        return self.filter_

    def save(self, account_email: str, filter_: GmailFilter) -> None:
        self.saves += 1


@dataclass
class FakeConfirmations:
    previews: dict[str, AnalysisPreview] = field(default_factory=dict)
    confirmations: dict[str, AnalysisConfirmation] = field(default_factory=dict)
    next_id: int = 0

    def save_preview(self, preview: AnalysisPreview) -> str:
        self.next_id += 1
        token = f"preview-{self.next_id}"
        self.previews[token] = preview
        return token

    def consume_preview(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisPreview | None:
        preview = self.previews.pop(token, None)
        return (
            preview
            if preview
            and preview.account_fingerprint == account_fingerprint
            and preview.expires_at > now
            else None
        )

    def save_confirmation(self, confirmation: AnalysisConfirmation) -> str:
        self.next_id += 1
        token = f"confirm-{self.next_id}"
        self.confirmations[token] = confirmation
        return token

    def consume_confirmation(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisConfirmation | None:
        confirmation = self.confirmations.pop(token, None)
        return (
            confirmation
            if confirmation
            and confirmation.account_fingerprint == account_fingerprint
            and confirmation.expires_at > now
            else None
        )


@dataclass
class FakePlanner:
    calls: int = 0

    def execute(
        self, account: str, candidates: list[ThreadCandidate], *, reanalysis: bool, filter_hash: str
    ) -> AnalysisRun:
        self.calls += 1
        return AnalysisRun.create(account, candidates)


@dataclass
class FakeSummarizer:
    calls: int = 0

    def execute(self, run: AnalysisRun, *, texts=None) -> AnalysisRun:
        self.calls += 1
        return run.finish("complete")


class FakeFinish:
    def execute(self, run: AnalysisRun, status: str, *, reason: str | None = None) -> AnalysisRun:
        return run.finish(status, reason)


@dataclass
class FakeState:
    summaries: tuple[ThreadSummary, ...] = ()

    def summaries_for_run(self, run_id: str) -> tuple[ThreadSummary, ...]:
        return self.summaries


def _service(
    gmail: FakeGmail, confirmations: FakeConfirmations, filters: FakeFilters | None = None
):
    account = hashlib.sha256(gmail.email.encode()).hexdigest()
    summaries = tuple(
        ThreadSummary(account, candidate.thread_id, "Krótko.", "niski", (), "openai")
        for candidate in gmail.candidates
    )
    return ConfirmedAdHocAnalysis(
        gmail,
        filters or FakeFilters(),
        confirmations,
        FakePlanner(),
        FakeFinish(),
        FakeSummarizer(),
        FakeState(summaries),
        provider="openai",
        now=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        preview_ttl=timedelta(minutes=5),
        confirmation_ttl=timedelta(minutes=5),
    )


def test_one_off_preview_is_ordered_and_does_not_fetch_body_or_change_active_filter() -> None:
    account = hashlib.sha256(b"owner@example.com").hexdigest()
    gmail = FakeGmail(
        candidates=[_candidate(account, "second", "2"), _candidate(account, "first", "1")],
        texts={"second": "Dwa", "first": "Jeden"},
    )
    filters, confirmations = FakeFilters(), FakeConfirmations()

    result = _service(gmail, confirmations, filters).preview(query=" label:ad-hoc ")

    assert result["status"] == "complete"
    assert result["data"] == {
        "phase": "preview",
        "query": "label:ad-hoc",
        "thread_ids": ["second", "first"],
        "thread_count": 2,
        "provider": "openai",
        "preview_token": "preview-1",
    }
    assert gmail.text_calls == 0
    assert filters.saves == 0


def test_invalid_confirmation_never_fetches_body_or_calls_analysis() -> None:
    gmail = FakeGmail(texts={})
    service = _service(gmail, FakeConfirmations())

    result = service.execute("missing")

    assert result["status"] == "failed"
    assert result["data"] is None
    assert result["next_action"] == "Refresh the preview and confirm it again."
    assert gmail.text_calls == 0


def test_confirmed_snapshot_executes_once_and_rejects_replay() -> None:
    account = hashlib.sha256(b"owner@example.com").hexdigest()
    gmail = FakeGmail(
        candidates=[_candidate(account, "thread", "message")], texts={"thread": "Treść"}
    )
    confirmations = FakeConfirmations()
    service = _service(gmail, confirmations)
    preview = service.preview()["data"]
    confirmation = service.confirm(preview["preview_token"])

    result = service.execute(confirmation["data"]["confirmation_token"])
    replay = service.execute(confirmation["data"]["confirmation_token"])

    assert result["status"] == "complete"
    assert result["data"]["provider"] == "openai"
    assert result["data"]["summaries"][0]["thread_id"] == "thread"
    assert replay["status"] == "failed"
    assert gmail.text_calls == 2  # one hash at confirmation, one verified hash at execution


def test_changed_input_after_confirmation_never_calls_provider() -> None:
    account = hashlib.sha256(b"owner@example.com").hexdigest()
    gmail = FakeGmail(
        candidates=[_candidate(account, "thread", "message")], texts={"thread": "Przed"}
    )
    confirmations = FakeConfirmations()
    service = _service(gmail, confirmations)
    preview = service.preview()["data"]
    confirmation = service.confirm(preview["preview_token"])
    gmail.texts["thread"] = "Po"

    result = service.execute(confirmation["data"]["confirmation_token"])

    assert result["status"] == "failed"
    assert "changed" in result["reason"].lower()


def test_claimed_confirmed_thread_is_failed_without_calling_provider() -> None:
    account = hashlib.sha256(b"owner@example.com").hexdigest()
    gmail = FakeGmail(
        candidates=[_candidate(account, "thread", "message")], texts={"thread": "Treść"}
    )

    class DroppingPlanner:
        def execute(self, account, candidates, *, reanalysis, filter_hash):
            return AnalysisRun.create(account, [])

    summarizer = FakeSummarizer()
    service = ConfirmedAdHocAnalysis(
        gmail,
        FakeFilters(),
        FakeConfirmations(),
        DroppingPlanner(),
        FakeFinish(),
        summarizer,
        FakeState(),
        provider="openai",
        now=lambda: datetime(2026, 7, 29, tzinfo=UTC),
    )
    preview = service.preview()["data"]
    confirmation = service.confirm(preview["preview_token"])

    result = service.execute(confirmation["data"]["confirmation_token"])

    assert result["status"] == "failed"
    assert summarizer.calls == 0
