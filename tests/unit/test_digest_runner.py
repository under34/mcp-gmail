from __future__ import annotations

from dataclasses import dataclass

from gmail_mcp.application.digest import RunDailyDigest
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.digest import Digest
from gmail_mcp.domain.thread_summary import ThreadSummary


@dataclass
class FakeRunner:
    run: AnalysisRun

    def execute(self) -> AnalysisRun:
        return self.run


@dataclass
class FakeDigests:
    saved: Digest | None = None


    def save_digest(self, digest: Digest) -> None:
        self.saved = digest

    def summaries_for_run(self, run_id: str):
        return ()

    def inclusion_reasons_for_run(self, run_id: str) -> dict[str, str]:
        return {}


@dataclass
class FakeSummaries:
    def execute(self, run: AnalysisRun) -> AnalysisRun:
        return run.finish("complete")


@dataclass
class PartialSummaries:
    def execute(self, run: AnalysisRun) -> AnalysisRun:
        return run.finish("partial", "One thread could not be completed.")


@dataclass
class FailingRunner:
    def execute(self) -> AnalysisRun:
        raise RuntimeError("secret must not escape")


def test_daily_digest_persists_a_complete_empty_run() -> None:
    repository = FakeDigests()
    result = RunDailyDigest(
        FakeRunner(AnalysisRun.create("account", [])), FakeSummaries(), repository, "openai"
    ).execute()

    assert result.status == "complete"
    assert repository.saved == result


def test_daily_digest_persists_a_safe_failure_without_exception_details() -> None:
    repository = FakeDigests()

    result = RunDailyDigest(FailingRunner(), FakeSummaries(), repository, "openai").execute()

    assert result.status == "failed"
    assert result.reason == "Daily digest could not be completed."
    assert result.next_action == "Retry later."
    assert "secret" not in result.reason


def test_daily_digest_keeps_the_provider_snapshot_for_a_partial_run() -> None:
    repository = FakeDigests()
    run = AnalysisRun.create(
        "account", [ThreadCandidate("account", "thread", "message", "now", "filter")]
    )

    result = RunDailyDigest(FakeRunner(run), PartialSummaries(), repository, "claude").execute()

    assert result.status == "partial"
    assert result.provider == "claude"


def test_daily_digest_preserves_the_planned_inclusion_reason() -> None:
    summary = ThreadSummary("account", "thread", "Krótko.", "niski", (), "openai")

    @dataclass
    class DigestRepository(FakeDigests):
        def summaries_for_run(self, run_id: str):
            return (summary,)

        def inclusion_reasons_for_run(self, run_id: str) -> dict[str, str]:
            return {"thread": "reanalysis"}

    repository = DigestRepository()
    run = AnalysisRun.create(
        "account", [ThreadCandidate("account", "thread", "message", "now", "filter")]
    )

    result = RunDailyDigest(FakeRunner(run), FakeSummaries(), repository, "openai").execute()

    assert result.items[0].inclusion_reason == "reanalysis"
