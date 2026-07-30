from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Protocol

from gmail_mcp.application.analysis_state import FinishAnalysis
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.thread_summary import ThreadSummary


class SummaryProviderUnavailableError(RuntimeError):
    """A provider failure affects every remaining request in the current run."""


class SummaryProviderAuthenticationError(SummaryProviderUnavailableError):
    """A provider rejected credentials; continuing would repeat the same request failure."""


class ThreadContentPort(Protocol):
    def fetch_clean_text(self, candidate: ThreadCandidate) -> str: ...


class SummaryProviderPort(Protocol):
    def summarize(
        self, *, account_fingerprint: str, thread_id: str, text: str
    ) -> ThreadSummary: ...


class ThreadSummaryRepositoryPort(Protocol):
    def save(self, summary: ThreadSummary, *, run_id: str, input_hash: str) -> None: ...


class SummarizeAnalysisRun:
    def __init__(
        self,
        content: ThreadContentPort,
        provider: SummaryProviderPort,
        summaries: ThreadSummaryRepositoryPort,
        finish: FinishAnalysis,
        provider_name: str = "selected",
    ) -> None:
        self._content = content
        self._provider = provider
        self._summaries = summaries
        self._finish = finish
        self._provider_name = provider_name
        self._logger = logging.getLogger("gmail_mcp")

    def execute(
        self,
        run: AnalysisRun,
        *,
        texts: Mapping[str, str] | None = None,
        expected_provider: str | None = None,
    ) -> AnalysisRun:
        successful: set[str] = set()
        for candidate in run.candidates:
            try:
                text = (
                    texts[candidate.thread_id]
                    if texts is not None
                    else self._content.fetch_clean_text(candidate)
                )
                summary = self._provider.summarize(
                    account_fingerprint=candidate.account_fingerprint,
                    thread_id=candidate.thread_id,
                    text=text,
                )
                if (
                    summary.provider not in {"openai", "claude"}
                    or (expected_provider is not None and summary.provider != expected_provider)
                    or summary.account_fingerprint != candidate.account_fingerprint
                    or summary.thread_id != candidate.thread_id
                    or summary.schema_version != 1
                    or summary.status != "complete"
                ):
                    raise ValueError("Invalid provider summary.")
                self._summaries.save(
                    summary,
                    run_id=run.run_id,
                    input_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )
                successful.add(candidate.thread_id)
            except SummaryProviderUnavailableError as error:
                # Do not retry the remaining threads: provider-wide failures are independent
                # of the thread and repeated attempts can send every matching email body.
                self._logger.warning(
                    "summary_provider_failure provider=%s exception_type=%s thread_id=%s",
                    expected_provider or self._provider_name,
                    type(error).__name__,
                    candidate.thread_id,
                )
                return self._finish.execute(
                    run,
                    "failed",
                    reason="The selected AI provider is unavailable. Check credentials or billing.",
                )
            except Exception as error:
                # Avoid exception messages and stack traces: provider responses can contain
                # email content or secrets. Exception type is sufficient for diagnosis.
                self._logger.warning(
                    "summary_provider_failure provider=%s exception_type=%s thread_id=%s",
                    expected_provider or self._provider_name,
                    type(error).__name__,
                    candidate.thread_id,
                )
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
