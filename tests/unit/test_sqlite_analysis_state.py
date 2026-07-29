from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import pytest

from gmail_mcp.adapters.sqlite_analysis_state import SqliteAnalysisStateAdapter
from gmail_mcp.application.analysis_state import AnalysisStateError, FinishAnalysis, PlanAnalysis
from gmail_mcp.domain.analysis_state import ThreadCandidate
from gmail_mcp.domain.digest import Digest
from gmail_mcp.domain.thread_summary import ThreadSummary


def _candidate(
    message_id: str = "message", thread_id: str = "thread", filter_hash: str = "filter"
) -> ThreadCandidate:
    return ThreadCandidate(
        "account", thread_id, message_id, "2026-07-28T00:00:00+00:00", filter_hash
    )


def test_sqlite_claims_a_candidate_only_once_while_it_is_running(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")

    first = state.plan("account", [_candidate()], filter_hash="filter")
    second = state.plan("account", [_candidate()], filter_hash="filter")

    assert len(first.candidates) == 1
    assert second.candidates == ()


def test_empty_plan_is_immediately_complete(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")

    run = state.plan("account", [], filter_hash="filter")

    assert run.status == "complete"


def test_sqlite_persists_validated_summary_without_thread_body(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    state = SqliteAnalysisStateAdapter(database)
    run = state.plan("account", [_candidate()], filter_hash="filter")
    summary = ThreadSummary("account", "thread", "Krótko.", "niski", (), "openai")

    state.save(summary, run_id=run.run_id, input_hash=sha256(b"sanitized input").hexdigest())

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT input_hash, summary, priority, actions_json, provider, status, reason, "
            "source_link, disclaimer "
            "FROM thread_summary"
        ).fetchone()
    assert row == (
        sha256(b"sanitized input").hexdigest(),
        "Krótko.",
        "niski",
        "[]",
        "openai",
        "complete",
        None,
        "https://mail.google.com/mail/u/0/#all/thread",
        "Wynik AI może być niepełny lub błędny.",
    )


def test_sqlite_replaces_legacy_summary_rows_without_required_provenance(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE thread_summary (account TEXT, thread_id TEXT, run_id TEXT, "
            "schema_version INTEGER, summary TEXT, priority TEXT, actions_json TEXT, "
            "provider TEXT, status TEXT, created_at TEXT)"
        )
        connection.execute(
            "INSERT INTO thread_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("account", "thread", "run", 1, "Krótko.", "niski", "[]", "openai", "complete", "now"),
        )

    SqliteAnalysisStateAdapter(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM thread_summary").fetchone() == (0,)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(thread_summary)")}
    assert {"input_hash", "source_link", "disclaimer"}.issubset(columns)


def test_sqlite_persists_digest_metadata_without_a_thread_body(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    state = SqliteAnalysisStateAdapter(database)
    state.save_digest(
        Digest("run", "account", "failed", "2026-07-29T08:00:00+00:00", None, None, 0, (),
               provider="openai", reason="Gmail is unavailable.", next_action="Reconnect Gmail.")
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT status, provider, reason, next_action FROM digest"
        ).fetchone()
        columns = {item[1] for item in connection.execute("PRAGMA table_info(digest)")}
    assert row == ("failed", "openai", "Gmail is unavailable.", "Reconnect Gmail.")
    assert "body" not in columns
    assert state.latest_digest("account").run_id == "run"  # type: ignore[union-attr]


def test_sqlite_rejects_a_summary_after_its_run_is_finished(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    run = state.plan("account", [_candidate()], filter_hash="filter")
    state.finish(run, "failed", reason="provider unavailable")

    with pytest.raises(AnalysisStateError, match="no longer active"):
        state.save(
            ThreadSummary("account", "thread", "Krótko.", "niski", (), "openai"),
            run_id=run.run_id,
            input_hash=sha256(b"sanitized input").hexdigest(),
        )


def test_expired_running_run_releases_its_claim_before_next_plan(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    state = SqliteAnalysisStateAdapter(database)
    stale = state.plan("account", [_candidate()], filter_hash="filter")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE analysis_run SET lease_expires_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00+00:00", stale.run_id),
        )

    retry = state.plan("account", [_candidate()], filter_hash="filter")

    assert len(retry.candidates) == 1


def test_sqlite_claims_thread_again_when_message_changes_or_reanalysis_is_requested(
    tmp_path,
) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    first = state.plan("account", [_candidate("one")], filter_hash="filter")
    state.finish(first, "complete")

    changed = state.plan("account", [_candidate("two")], filter_hash="filter")
    state.finish(changed, "complete")
    forced = state.plan("account", [_candidate("two")], reanalysis=True, filter_hash="filter")

    assert len(changed.candidates) == 1
    assert len(forced.candidates) == 1


def test_filter_membership_requalifies_a_thread_that_leaves_and_rejoins(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    first = state.plan("account", [_candidate()], filter_hash="filter")
    state.finish(first, "complete")

    state.plan("account", [], filter_hash="filter")
    rejoined = state.plan("account", [_candidate()], filter_hash="filter")

    assert len(rejoined.candidates) == 1


def test_failed_candidates_are_released_for_a_future_run(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    first = state.plan("account", [_candidate()], filter_hash="filter")
    state.finish(first, "failed", reason="provider unavailable")

    retry = state.plan("account", [_candidate()], filter_hash="filter")

    assert len(retry.candidates) == 1


def test_partial_run_releases_only_unsuccessful_candidates(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    first = state.plan(
        "account", [_candidate(thread_id="one"), _candidate(thread_id="two")], filter_hash="filter"
    )
    state.finish(first, "partial", successful_thread_ids={"one"}, reason="one provider error")

    retry = state.plan(
        "account", [_candidate(thread_id="one"), _candidate(thread_id="two")], filter_hash="filter"
    )

    assert [candidate.thread_id for candidate in retry.candidates] == ["two"]


def test_application_planning_returns_no_duplicate_after_first_claim(tmp_path) -> None:
    planner = PlanAnalysis(SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3"))

    first = planner.execute("account", [_candidate()], filter_hash="filter")
    second = planner.execute("account", [_candidate()], filter_hash="filter")

    assert len(first.candidates) == 1
    assert second.candidates == ()


def test_sqlite_persists_run_snapshot_in_input_order(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")

    run = state.plan(
        "account",
        [_candidate("one", "thread-two"), _candidate("two", "thread")],
        filter_hash="filter",
    )

    assert state.run_snapshot(run.run_id) == (
        ("thread-two", "one", "filter"),
        ("thread", "two", "filter"),
    )


def test_duplicate_thread_metadata_is_deduplicated_before_snapshot_insert(tmp_path) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")

    run = state.plan("account", [_candidate(), _candidate()], reanalysis=True, filter_hash="filter")

    assert len(run.candidates) == 1


def test_concurrent_plans_claim_a_thread_only_once(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"

    def plan_once() -> int:
        run = SqliteAnalysisStateAdapter(database).plan(
            "account", [_candidate()], filter_hash="filter"
        )
        return len(run.candidates)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(lambda _: plan_once(), range(2)))

    assert sorted(claims) == [0, 1]


def test_terminal_status_is_persisted_and_cannot_be_overwritten(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    state = SqliteAnalysisStateAdapter(database)
    run = state.plan("account", [_candidate()], filter_hash="filter")

    assert state.finish(run, "complete").status == "complete"
    assert state.finish(run, "failed", reason="stale worker").status == "complete"
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT status FROM analysis_run WHERE run_id = ?", (run.run_id,)
        ).fetchone() == ("complete",)


def test_finish_use_case_returns_a_safe_failure_when_state_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    state = SqliteAnalysisStateAdapter(tmp_path / "state.sqlite3")
    run = state.plan("account", [_candidate()], filter_hash="filter")
    monkeypatch.setattr(
        state, "finish", lambda *args, **kwargs: (_ for _ in ()).throw(AnalysisStateError())
    )

    result = FinishAnalysis(state).execute(run, "complete")

    assert result.status == "failed"
    assert result.reason == "Local analysis state is unavailable."
