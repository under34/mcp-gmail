from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from gmail_mcp.domain.analysis_state import AnalysisRun
from gmail_mcp.domain.digest import Digest, DigestItem
from gmail_mcp.domain.thread_summary import ThreadSummary


class DigestRepositoryPort(Protocol):
    def save_digest(self, digest: Digest) -> None: ...

    def summaries_for_run(self, run_id: str) -> tuple[ThreadSummary, ...]: ...


class DigestRunnerPort(Protocol):
    def execute(self) -> AnalysisRun: ...


class SummaryRunnerPort(Protocol):
    def execute(self, run: AnalysisRun) -> AnalysisRun: ...


class RunDailyDigest:
    def __init__(
        self,
        run_analysis: DigestRunnerPort,
        summarize: SummaryRunnerPort,
        digests: DigestRepositoryPort,
        provider: str,
    ) -> None:
        self._run_analysis = run_analysis
        self._summarize = summarize
        self._digests = digests
        self._provider = provider

    def execute(self) -> Digest:
        try:
            run = self._run_analysis.execute()
            if run.status == "running":
                run = self._summarize.execute(run)
        except Exception:
            run = AnalysisRun.failed("", "Daily digest could not be completed.")
        try:
            summaries = self._digests.summaries_for_run(run.run_id)
        except Exception:
            run = AnalysisRun.failed(run.account_fingerprint, "Digest summaries are unavailable.")
            summaries = ()
        action = "Retry later."
        digest = Digest(
            run_id=run.run_id,
            account_fingerprint=run.account_fingerprint,
            status=run.status,  # type: ignore[arg-type]
            generated_at=datetime.now(UTC).isoformat(),
            covered_from=run.covered_from,
            covered_to=run.covered_to,
            matching_thread_count=len(run.candidates),
            items=tuple(DigestItem(summary, "new_message") for summary in summaries),
            provider=self._provider,
            reason=run.reason,
            next_action=None if run.status == "complete" else action,
        )
        try:
            self._digests.save_digest(digest)
        except Exception:
            return Digest(
                run_id=run.run_id,
                account_fingerprint=run.account_fingerprint,
                status="failed",
                generated_at=digest.generated_at,
                covered_from=run.covered_from,
                covered_to=run.covered_to,
                matching_thread_count=0,
                items=(),
                provider=self._provider,
                reason="Local digest state is unavailable.",
                next_action="Check local storage and retry later.",
            )
        return digest
