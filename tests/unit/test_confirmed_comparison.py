from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from gmail_mcp.application.confirmed_comparison import ConfirmedComparison
from gmail_mcp.domain.analysis_state import ThreadCandidate
from gmail_mcp.domain.confirmation import AnalysisConfirmation, AnalysisPreview
from gmail_mcp.domain.gmail_filter import GmailFilter
from gmail_mcp.domain.thread_summary import ThreadSummary


def _account() -> str:
    return hashlib.sha256(b"owner@example.com").hexdigest()


@dataclass
class Gmail:
    candidates: list[ThreadCandidate]
    texts: dict[str, str]
    text_calls: int = 0

    def current_account_email(self) -> str:
        return "owner@example.com"

    def find_thread_candidates(self, account, query, filter_hash):
        return [
            ThreadCandidate(
                account, c.thread_id, c.latest_message_id, c.latest_message_at, filter_hash
            )
            for c in self.candidates
        ]

    def fetch_clean_text(self, candidate):
        self.text_calls += 1
        return self.texts[candidate.thread_id]


@dataclass
class Filters:
    query: str = "label:work"

    def load(self, email):
        return GmailFilter(self.query)


@dataclass
class Tokens:
    previews: dict[str, AnalysisPreview] = field(default_factory=dict)
    confirmations: dict[str, AnalysisConfirmation] = field(default_factory=dict)

    def save_preview(self, value):
        self.previews["p"] = value
        return "p"

    def consume_preview(self, token, *, account_fingerprint, now):
        value = self.previews.get(token)
        if (
            value is None
            or value.account_fingerprint != account_fingerprint
            or value.expires_at <= now
        ):
            return None
        return self.previews.pop(token)

    def save_confirmation(self, value):
        self.confirmations["c"] = value
        return "c"

    def consume_confirmation(self, token, *, account_fingerprint, now):
        value = self.confirmations.get(token)
        if (
            value is None
            or value.account_fingerprint != account_fingerprint
            or value.expires_at <= now
        ):
            return None
        return self.confirmations.pop(token)


@dataclass
class Provider:
    name: str
    fail: bool = False
    calls: list[str] = field(default_factory=list)

    def summarize(self, *, account_fingerprint, thread_id, text):
        self.calls.append(text)
        if self.fail:
            raise ValueError("provider failed")
        return ThreadSummary(account_fingerprint, thread_id, "Krótko.", "niski", (), self.name)


@dataclass
class MalformedProvider:
    calls: list[str] = field(default_factory=list)

    def summarize(self, *, account_fingerprint, thread_id, text):
        self.calls.append(text)
        return None


def _service(gmail, openai=None, claude=None, filters=None):
    return ConfirmedComparison(
        gmail,
        filters or Filters(),
        Tokens(),
        {"openai": openai or Provider("openai"), "claude": claude or Provider("claude")},
        now=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        ttl=timedelta(minutes=5),
    )


def test_out_of_filter_thread_never_fetches_body_or_calls_provider() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "allowed", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"allowed": "text"},
    )
    service = _service(gmail)
    result = service.preview("outside")
    assert result["status"] == "failed"
    assert gmail.text_calls == 0


def test_comparison_returns_partial_and_same_input_for_both_providers() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "same text"},
    )
    openai, claude = Provider("openai"), Provider("claude", fail=True)
    service = _service(gmail, openai, claude)
    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])
    result = service.execute(confirmation["data"]["confirmation_token"])
    assert result["status"] == "partial"
    assert openai.calls == claude.calls == ["same text"]
    assert result["data"]["results"][0]["provider"] == "openai"
    assert result["data"]["results"][1]["status"] == "failed"


def test_invalid_or_replayed_token_never_fetches_text_or_calls_provider() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "same text"},
    )
    openai, claude = Provider("openai"), Provider("claude")
    service = _service(gmail, openai, claude)

    assert service.execute(None)["status"] == "failed"
    assert service.execute("missing")["status"] == "failed"
    assert gmail.text_calls == 0
    assert openai.calls == claude.calls == []

    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])["data"]
    assert service.execute(confirmation["confirmation_token"])["status"] == "complete"
    assert service.execute(confirmation["confirmation_token"])["status"] == "failed"
    assert openai.calls == claude.calls == ["same text"]


def test_changed_input_fails_before_provider_calls() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "before"},
    )
    openai, claude = Provider("openai"), Provider("claude")
    service = _service(gmail, openai, claude)
    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])["data"]
    gmail.texts["thread"] = "after"

    assert service.execute(confirmation["confirmation_token"])["status"] == "failed"
    assert openai.calls == claude.calls == []


def test_changed_active_filter_fails_before_body_access() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "same text"},
    )
    openai, claude = Provider("openai"), Provider("claude")
    filters = Filters()
    service = _service(gmail, openai, claude, filters)
    preview = service.preview("thread")["data"]
    filters.query = "label:other"

    assert service.confirm(preview["preview_token"])["status"] == "failed"
    assert gmail.text_calls == 0
    assert openai.calls == claude.calls == []


def test_removed_candidate_after_confirmation_fails_before_second_body_access() -> None:
    account = _account()
    candidate = ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")
    gmail = Gmail([candidate], {"thread": "same text"})
    openai, claude = Provider("openai"), Provider("claude")
    service = _service(gmail, openai, claude)
    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])["data"]
    gmail.candidates = []

    assert service.execute(confirmation["confirmation_token"])["status"] == "failed"
    assert gmail.text_calls == 1
    assert openai.calls == claude.calls == []


def test_both_provider_failures_return_failed_after_one_call_each() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "same text"},
    )
    openai, claude = Provider("openai", fail=True), Provider("claude", fail=True)
    service = _service(gmail, openai, claude)
    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])["data"]

    result = service.execute(confirmation["confirmation_token"])
    assert result["status"] == "failed"
    assert [item["reason"] for item in result["data"]["results"]] == [
        "Provider request failed.",
        "Provider request failed.",
    ]
    assert openai.calls == claude.calls == ["same text"]


def test_malformed_provider_result_does_not_block_other_provider() -> None:
    account = _account()
    gmail = Gmail(
        [ThreadCandidate(account, "thread", "m", "2026-07-29T00:00:00+00:00", "x")],
        {"thread": "same text"},
    )
    openai, claude = MalformedProvider(), Provider("claude")
    service = _service(gmail, openai, claude)
    preview = service.preview("thread")["data"]
    confirmation = service.confirm(preview["preview_token"])["data"]

    result = service.execute(confirmation["confirmation_token"])
    assert result["status"] == "partial"
    assert result["data"]["results"][0]["reason"] == "Provider returned an invalid summary."
    assert openai.calls == claude.calls == ["same text"]
