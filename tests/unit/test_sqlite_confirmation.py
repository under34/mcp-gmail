from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from gmail_mcp.adapters.sqlite_analysis_state import SqliteAnalysisStateAdapter
from gmail_mcp.adapters.sqlite_confirmation import SqliteConfirmationAdapter
from gmail_mcp.domain.analysis_state import ThreadCandidate
from gmail_mcp.domain.confirmation import AnalysisConfirmation, AnalysisPreview, filter_hash


def _preview(now: datetime) -> AnalysisPreview:
    account = "account"
    query = "label:work"
    return AnalysisPreview(
        account,
        "summarize_gmail",
        query,
        filter_hash(query),
        (
            ThreadCandidate(
                account, "thread", "message", "2026-07-29T08:00:00+00:00", filter_hash(query)
            ),
        ),
        "openai",
        now + timedelta(minutes=5),
    )


def test_sqlite_confirmation_is_opaque_single_use_and_stores_only_metadata(tmp_path) -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    path = tmp_path / "state.sqlite3"
    store = SqliteConfirmationAdapter(path)
    token = store.save_preview(_preview(now))

    consumed = store.consume_preview(token, account_fingerprint="account", now=now)
    replay = store.consume_preview(token, account_fingerprint="account", now=now)

    assert consumed is not None
    assert replay is None
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT token_hash, candidates_json FROM analysis_confirmation"
        ).fetchone()
    assert row is not None
    assert token != row[0]
    assert "thread" in row[1]
    assert "Treść wiadomości" not in row[1]


def test_sqlite_confirmation_rejects_expired_or_other_account(tmp_path) -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    store = SqliteConfirmationAdapter(tmp_path / "state.sqlite3")
    token = store.save_preview(_preview(now))

    assert store.consume_preview(token, account_fingerprint="other", now=now) is None
    assert store.consume_preview(token, account_fingerprint="account", now=now) is not None

    expired = AnalysisConfirmation(
        "account",
        "summarize_gmail",
        "label:work",
        filter_hash("label:work"),
        (),
        "openai",
        "a" * 64,
        now - timedelta(seconds=1),
    )
    expired_token = store.save_confirmation(expired)
    assert store.consume_confirmation(expired_token, account_fingerprint="account", now=now) is None


def test_corrupted_confirmation_snapshot_is_rejected_before_consumption(tmp_path) -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    path = tmp_path / "state.sqlite3"
    store = SqliteConfirmationAdapter(path)
    token = store.save_preview(_preview(now))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE analysis_confirmation SET candidates_json = ?", ('[["other", "m", "t", "x"]]',)
        )

    assert store.consume_preview(token, account_fingerprint="account", now=now) is None


def test_account_deletion_removes_pending_confirmations(tmp_path) -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    path = tmp_path / "state.sqlite3"
    store = SqliteConfirmationAdapter(path)
    store.save_preview(_preview(now))
    state = SqliteAnalysisStateAdapter(path)

    state.begin_account_deletion("account")
    state.delete_account_data("account")

    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM analysis_confirmation").fetchone()[0]
    assert count == 0
