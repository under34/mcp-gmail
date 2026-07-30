import logging
from dataclasses import dataclass, field

from gmail_mcp.application.thread_summary import (
    SummarizeAnalysisRun,
    SummaryProviderAuthenticationError,
)
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.thread_summary import ThreadSummary


@dataclass
class FakeContent:
    def fetch_clean_text(self, candidate: ThreadCandidate) -> str:
        if candidate.thread_id == "bad":
            raise ValueError()
        return "Tekst"


@dataclass
class FakeProvider:
    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        return ThreadSummary(account_fingerprint, thread_id, "Krótko.", "niski", (), "openai")


@dataclass
class FailingProvider:
    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        raise RuntimeError("mail content and api-key-should-not-appear")


@dataclass
class AuthenticationFailingProvider:
    calls: list[str] = field(default_factory=list)

    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        self.calls.append(thread_id)
        raise SummaryProviderAuthenticationError("api-key-should-not-appear")


@dataclass
class FakeSummaries:
    saved: list[str] = field(default_factory=list)

    def save(self, summary: ThreadSummary, *, run_id: str, input_hash: str) -> None:
        self.saved.append(summary.thread_id)


@dataclass
class FakeFinish:
    status: str | None = None
    successful: set[str] | None = None
    def execute(self, run, status, *, successful_thread_ids=None, reason=None):
        self.status, self.successful = status, successful_thread_ids
        return run.finish(status, reason)


def _capture_application_logs(monkeypatch, caplog) -> None:
    logger = logging.getLogger("gmail_mcp")
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "propagate", True)
    caplog.set_level(logging.WARNING, logger="gmail_mcp")


def test_summary_run_is_partial_when_one_thread_fails() -> None:
    run = AnalysisRun.create("account", [
        ThreadCandidate("account", "good", "1", "2026-01-01T00:00:00+00:00", "filter"),
        ThreadCandidate("account", "bad", "2", "2026-01-01T00:00:00+00:00", "filter"),
    ])
    summaries, finish = FakeSummaries(), FakeFinish()

    result = SummarizeAnalysisRun(FakeContent(), FakeProvider(), summaries, finish).execute(run)

    assert result.status == "partial"
    assert summaries.saved == ["good"]
    assert finish.successful == {"good"}


def test_summary_run_rejects_a_summary_from_an_unexpected_provider() -> None:
    run = AnalysisRun.create(
        "account", [ThreadCandidate("account", "good", "1", "2026-01-01T00:00:00+00:00", "filter")]
    )
    summaries, finish = FakeSummaries(), FakeFinish()

    result = SummarizeAnalysisRun(FakeContent(), FakeProvider(), summaries, finish).execute(
        run, expected_provider="claude"
    )

    assert result.status == "failed"
    assert summaries.saved == []


def test_summary_run_logs_only_safe_provider_failure_metadata(monkeypatch, caplog) -> None:
    _capture_application_logs(monkeypatch, caplog)
    run = AnalysisRun.create(
        "account",
        [ThreadCandidate("account", "thread-id", "1", "2026-01-01T00:00:00+00:00", "filter")],
    )

    result = SummarizeAnalysisRun(
        FakeContent(), FailingProvider(), FakeSummaries(), FakeFinish()
    ).execute(run, expected_provider="claude")

    assert result.status == "failed"
    assert (
        "summary_provider_failure provider=claude exception_type=RuntimeError thread_id=thread-id"
        in caplog.text
    )
    assert "mail content" not in caplog.text
    assert "api-key-should-not-appear" not in caplog.text


def test_summary_run_fails_fast_when_provider_rejects_credentials(monkeypatch, caplog) -> None:
    _capture_application_logs(monkeypatch, caplog)
    run = AnalysisRun.create("account", [
        ThreadCandidate("account", "first", "1", "2026-01-01T00:00:00+00:00", "filter"),
        ThreadCandidate("account", "second", "2", "2026-01-01T00:00:00+00:00", "filter"),
    ])
    provider, summaries, finish = AuthenticationFailingProvider(), FakeSummaries(), FakeFinish()

    result = SummarizeAnalysisRun(FakeContent(), provider, summaries, finish).execute(
        run, expected_provider="claude"
    )

    assert result.status == "failed"
    assert result.reason == "The selected AI provider is unavailable. Check credentials or billing."
    assert provider.calls == ["first"]
    assert summaries.saved == []
    assert "SummaryProviderAuthenticationError" in caplog.text
    assert "api-key-should-not-appear" not in caplog.text
