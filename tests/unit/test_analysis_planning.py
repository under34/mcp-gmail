from __future__ import annotations

from dataclasses import dataclass

from gmail_mcp.application.analysis_state import PlanActiveFilterAnalysis
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate
from gmail_mcp.domain.gmail_filter import GmailFilter


@dataclass
class FakeFilters:
    filter_: GmailFilter | None = GmailFilter("label:work")
    def load(self, account_email: str) -> GmailFilter | None: return self.filter_


class FakeGmail:
    def current_account_email(self) -> str:
        return "owner@example.com"

    def find_thread_candidates(
        self, account: str, query: str, filter_hash: str
    ) -> list[ThreadCandidate]:
        return [
            ThreadCandidate(
                account, "thread", "message", "2026-07-28T00:00:00+00:00", filter_hash
            )
        ]


class FakeState:
    def plan(
        self,
        account: str,
        candidates: list[ThreadCandidate],
        *,
        reanalysis: bool = False,
        filter_hash: str | None = None,
    ) -> AnalysisRun:
        return AnalysisRun.create(account, candidates)


def test_active_filter_analysis_uses_saved_filter_and_thread_candidates() -> None:
    run = PlanActiveFilterAnalysis(FakeGmail(), FakeFilters(), FakeState()).execute()

    assert run.status == "running"
    assert run.candidates[0].thread_id == "thread"
