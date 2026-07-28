from __future__ import annotations

from typing import Protocol

from gmail_mcp.application.analysis_state import FinishAnalysis
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.thread_summary import ThreadSummary


class ThreadContentPort(Protocol):
    def fetch_clean_text(self, candidate: ThreadCandidate) -> str: ...


class SummaryProviderPort(Protocol):
    def summarize(
        self, *, account_fingerprint: str, thread_id: str, text: str
    ) -> ThreadSummary: ...


class ThreadSummaryRepositoryPort(Protocol):
    def save(self, summary: ThreadSummary, *, run_id: str) -> None: ...


class SummarizeAnalysisRun:
    def __init__(
        self,
        content: ThreadContentPort,
        provider: SummaryProviderPort,
        summaries: ThreadSummaryRepositoryPort,
        finish: FinishAnalysis,
    ) -> None:
        self._content = content
        self._provider = provider
        self._summaries = summaries
        self._finish = finish

    def execute(self, run: AnalysisRun) -> AnalysisRun:
        successful: set[str] = set()
        for candidate in run.candidates:
            try:
                text = self._content.fetch_clean_text(candidate)
                summary = self._provider.summarize(
                    account_fingerprint=candidate.account_fingerprint,
                    thread_id=candidate.thread_id,
                    text=text,
                )
                if (
                    summary.provider not in {"openai", "claude"}
                    or summary.thread_id != candidate.thread_id
                ):
                    raise ValueError("Invalid provider summary.")
                self._summaries.save(summary, run_id=run.run_id)
                successful.add(candidate.thread_id)
            except Exception:
                continue
        if len(successful) == len(run.candidates):
            return self._finish.execute(run, "complete")
        if successful:
            return self._finish.execute(
                run,
                "partial",
                successful_thread_ids=successful,
                reason="Some thread summaries could not be completed.",
            )
        return self._finish.execute(
            run, "failed", reason="Thread summaries could not be completed."
        )
