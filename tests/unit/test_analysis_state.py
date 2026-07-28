from __future__ import annotations

from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate


def test_candidate_is_identified_by_account_thread_and_latest_message() -> None:
    candidate = ThreadCandidate(
        account_fingerprint="account",
        thread_id="thread",
        latest_message_id="message",
        latest_message_at="2026-07-28T00:00:00+00:00",
        filter_hash="filter",
    )

    assert candidate.thread_id == "thread"


def test_analysis_run_keeps_an_immutable_candidate_snapshot() -> None:
    candidate = ThreadCandidate(
        "account", "thread", "message", "2026-07-28T00:00:00+00:00", "filter"
    )
    run = AnalysisRun.create("account", [candidate])

    assert run.status == "running"
    assert run.candidates == (candidate,)
    assert run.input_hash


def test_analysis_run_accepts_only_terminal_truthful_statuses() -> None:
    run = AnalysisRun.create("account", [])

    assert run.finish("partial", "provider unavailable").status == "partial"
