from dataclasses import dataclass, field

from gmail_mcp.application.thread_summary import SummarizeAnalysisRun
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
