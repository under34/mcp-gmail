from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gmail_mcp.application.analysis_state import AnalysisStateError
from gmail_mcp.domain.analysis_state import AnalysisRun, ThreadCandidate


class SqliteAnalysisStateAdapter:
    """Single-writer local state; stores only thread metadata and input hashes."""

    _LEASE_DURATION = timedelta(minutes=15)

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, isolation_level=None)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS thread_state (
                    account TEXT NOT NULL, thread_id TEXT NOT NULL,
                    latest_message_id TEXT NOT NULL,
                    PRIMARY KEY (account, thread_id))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_claim (
                    account TEXT NOT NULL, thread_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    PRIMARY KEY (account, thread_id))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS filter_membership (
                    account TEXT NOT NULL, filter_hash TEXT NOT NULL, thread_id TEXT NOT NULL,
                    is_matching INTEGER NOT NULL, PRIMARY KEY (account, filter_hash, thread_id))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_run_candidate (
                    run_id TEXT NOT NULL, thread_id TEXT NOT NULL, latest_message_id TEXT NOT NULL,
                    latest_message_at TEXT NOT NULL, filter_hash TEXT NOT NULL,
                    position INTEGER NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY (run_id, thread_id))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_run (
                    run_id TEXT PRIMARY KEY, account TEXT NOT NULL, input_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL, lease_expires_at TEXT NOT NULL,
                    covered_from TEXT, covered_to TEXT, status TEXT NOT NULL,
                    reanalysis INTEGER NOT NULL, reason TEXT)"""
            )

    def plan(
        self,
        account_fingerprint: str,
        candidates: list[ThreadCandidate],
        *,
        reanalysis: bool = False,
        filter_hash: str,
    ) -> AnalysisRun:
        unique = self._unique_candidates(account_fingerprint, candidates)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._recover_expired_runs(connection)
                self._mark_missing_memberships(
                    connection, account_fingerprint, unique, filter_hash=filter_hash
                )
                claimed: list[ThreadCandidate] = []
                for candidate in unique:
                    membership = connection.execute(
                        "SELECT is_matching FROM filter_membership WHERE account = ? "
                        "AND filter_hash = ? AND thread_id = ?",
                        (account_fingerprint, candidate.filter_hash, candidate.thread_id),
                    ).fetchone()
                    state = connection.execute(
                        "SELECT latest_message_id FROM thread_state "
                        "WHERE account = ? AND thread_id = ?",
                        (account_fingerprint, candidate.thread_id),
                    ).fetchone()
                    active_claim = connection.execute(
                        "SELECT 1 FROM analysis_claim WHERE account = ? AND thread_id = ?",
                        (account_fingerprint, candidate.thread_id),
                    ).fetchone()
                    newly_matching = membership is None or not bool(membership[0])
                    message_changed = state is None or state[0] != candidate.latest_message_id
                    if active_claim is None and (reanalysis or newly_matching or message_changed):
                        claimed.append(candidate)
                    connection.execute(
                        "INSERT INTO filter_membership("
                        "account, filter_hash, thread_id, is_matching) "
                        "VALUES (?, ?, ?, 1) ON CONFLICT(account, filter_hash, thread_id) "
                        "DO UPDATE SET is_matching=1",
                        (account_fingerprint, candidate.filter_hash, candidate.thread_id),
                    )
                run = AnalysisRun.create(account_fingerprint, claimed)
                connection.execute(
                    "INSERT INTO analysis_run("
                    "run_id, account, input_hash, created_at, lease_expires_at, covered_from, "
                    "covered_to, status, reanalysis, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run.run_id,
                        account_fingerprint,
                        run.input_hash,
                        run.created_at,
                        (datetime.fromisoformat(run.created_at) + self._LEASE_DURATION).isoformat(),
                        run.covered_from,
                        run.covered_to,
                        "complete" if not claimed else run.status,
                        int(reanalysis),
                        None,
                    ),
                )
                connection.executemany(
                    "INSERT INTO analysis_claim(account, thread_id, run_id) VALUES (?, ?, ?)",
                    [(account_fingerprint, item.thread_id, run.run_id) for item in claimed],
                )
                connection.executemany(
                    "INSERT INTO analysis_run_candidate(run_id, thread_id, latest_message_id, "
                    "latest_message_at, filter_hash, position, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'running')",
                    [
                        (
                            run.run_id,
                            item.thread_id,
                            item.latest_message_id,
                            item.latest_message_at,
                            item.filter_hash,
                            position,
                        )
                        for position, item in enumerate(claimed)
                    ],
                )
            return run.finish("complete") if not claimed else run
        except sqlite3.Error as error:
            raise AnalysisStateError("Local analysis state is unavailable.") from error

    def run_snapshot(self, run_id: str) -> tuple[tuple[str, str, str], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT thread_id, latest_message_id, filter_hash FROM analysis_run_candidate "
                "WHERE run_id = ? ORDER BY position",
                (run_id,),
            ).fetchall()
        return tuple((str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def finish(
        self,
        run: AnalysisRun,
        status: str,
        *,
        successful_thread_ids: set[str] | None = None,
        reason: str | None = None,
    ) -> AnalysisRun:
        finished = run.finish(status, reason)
        candidate_ids = {candidate.thread_id for candidate in run.candidates}
        successful = candidate_ids if status == "complete" else successful_thread_ids or set()
        if not successful.issubset(candidate_ids):
            raise AnalysisStateError("Successful threads do not belong to this analysis run.")
        if status == "partial" and successful_thread_ids is None:
            raise AnalysisStateError("Partial analysis requires successful thread identifiers.")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                stored = connection.execute(
                    "SELECT account, input_hash, status, reason FROM analysis_run WHERE run_id = ?",
                    (run.run_id,),
                ).fetchone()
                if stored is None:
                    raise AnalysisStateError("Analysis run does not exist.")
                if stored[0] != run.account_fingerprint or stored[1] != run.input_hash:
                    raise AnalysisStateError("Analysis run does not match its persisted snapshot.")
                snapshot = tuple(
                    ThreadCandidate(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))
                    for row in connection.execute(
                        "SELECT ?, thread_id, latest_message_id, latest_message_at, filter_hash "
                        "FROM analysis_run_candidate WHERE run_id = ? ORDER BY position",
                        (run.account_fingerprint, run.run_id),
                    ).fetchall()
                )
                if snapshot != run.candidates:
                    raise AnalysisStateError("Analysis run does not match its persisted snapshot.")
                if stored[2] != "running":
                    return run.finish(str(stored[2]), stored[3])
                for candidate in run.candidates:
                    candidate_status = "complete" if candidate.thread_id in successful else "failed"
                    connection.execute(
                        "UPDATE analysis_run_candidate SET status = ? "
                        "WHERE run_id = ? AND thread_id = ?",
                        (candidate_status, run.run_id, candidate.thread_id),
                    )
                    if candidate_status == "complete":
                        connection.execute(
                            "INSERT INTO thread_state("
                            "account, thread_id, latest_message_id) VALUES (?, ?, ?) "
                            "ON CONFLICT(account, thread_id) DO UPDATE SET "
                            "latest_message_id=excluded.latest_message_id",
                            (
                                run.account_fingerprint,
                                candidate.thread_id,
                                candidate.latest_message_id,
                            ),
                        )
                connection.execute("DELETE FROM analysis_claim WHERE run_id = ?", (run.run_id,))
                connection.execute(
                    "UPDATE analysis_run SET status = ?, reason = ? "
                    "WHERE run_id = ? AND status = 'running'",
                    (finished.status, finished.reason, run.run_id),
                )
            return finished
        except sqlite3.Error as error:
            raise AnalysisStateError("Local analysis state is unavailable.") from error

    @staticmethod
    def _unique_candidates(
        account_fingerprint: str, candidates: list[ThreadCandidate]
    ) -> list[ThreadCandidate]:
        unique: dict[str, ThreadCandidate] = {}
        for candidate in candidates:
            if candidate.account_fingerprint != account_fingerprint:
                raise AnalysisStateError("Candidate account does not match analysis account.")
            existing = unique.setdefault(candidate.thread_id, candidate)
            if existing != candidate:
                raise AnalysisStateError("Conflicting candidates for one Gmail thread.")
        return list(unique.values())

    @staticmethod
    def _mark_missing_memberships(
        connection: sqlite3.Connection,
        account_fingerprint: str,
        candidates: list[ThreadCandidate],
        *,
        filter_hash: str,
    ) -> None:
        by_filter: dict[str, list[str]] = {}
        for candidate in candidates:
            by_filter.setdefault(candidate.filter_hash, []).append(candidate.thread_id)
        by_filter.setdefault(filter_hash, [])
        for filter_hash, thread_ids in by_filter.items():
            if thread_ids:
                placeholders = ", ".join("?" for _ in thread_ids)
                connection.execute(
                    "UPDATE filter_membership SET is_matching = 0 WHERE account = ? "
                    "AND filter_hash = ? AND is_matching = 1 "
                    f"AND thread_id NOT IN ({placeholders})",
                    (account_fingerprint, filter_hash, *thread_ids),
                )
            else:
                connection.execute(
                    "UPDATE filter_membership SET is_matching = 0 WHERE account = ? "
                    "AND filter_hash = ? AND is_matching = 1",
                    (account_fingerprint, filter_hash),
                )

    @staticmethod
    def _recover_expired_runs(connection: sqlite3.Connection) -> None:
        now = datetime.now(UTC).isoformat()
        expired = connection.execute(
            "SELECT run_id FROM analysis_run "
            "WHERE status = 'running' AND lease_expires_at <= ?",
            (now,),
        ).fetchall()
        for (run_id,) in expired:
            connection.execute(
                "UPDATE analysis_run SET status = 'failed', reason = ? WHERE run_id = ?",
                ("Analysis lease expired.", run_id),
            )
            connection.execute(
                "UPDATE analysis_run_candidate SET status = 'failed' WHERE run_id = ?", (run_id,)
            )
            connection.execute("DELETE FROM analysis_claim WHERE run_id = ?", (run_id,))
