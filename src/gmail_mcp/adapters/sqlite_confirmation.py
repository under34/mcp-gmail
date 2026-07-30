from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from gmail_mcp.domain.analysis_state import ThreadCandidate
from gmail_mcp.domain.confirmation import AnalysisConfirmation, AnalysisPreview, snapshot_hash


class SqliteConfirmationAdapter:
    """Private metadata-only, single-use confirmation storage."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_confirmation (
                    token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL, account TEXT NOT NULL,
                    operation TEXT NOT NULL, query TEXT NOT NULL, filter_hash TEXT NOT NULL,
                    candidates_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL, input_hash TEXT,
                    expires_at TEXT NOT NULL, consumed_at TEXT)"""
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(analysis_confirmation)")
            }
            if "snapshot_hash" not in columns:
                connection.execute(
                    "ALTER TABLE analysis_confirmation ADD COLUMN "
                    "snapshot_hash TEXT NOT NULL DEFAULT ''"
                )
            connection.execute("UPDATE analysis_confirmation SET query = '' WHERE query <> ''")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS account_execution_lease (
                    account TEXT PRIMARY KEY, token TEXT NOT NULL, owner_pid INTEGER NOT NULL)"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, isolation_level=None)

    def save_preview(self, preview: AnalysisPreview) -> str:
        return self._save("preview", preview, input_hash=None)

    def consume_preview(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisPreview | None:
        row = self._consume("preview", token, account_fingerprint, now)
        if row is None:
            return None
        return AnalysisPreview(*row[:6], expires_at=datetime.fromisoformat(row[7]))

    def save_confirmation(self, confirmation: AnalysisConfirmation) -> str:
        return self._save("confirmation", confirmation, input_hash=confirmation.input_hash)

    def acquire_execution_lease(self, account_fingerprint: str) -> str | None:
        token = secrets.token_urlsafe(32)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if self._deletion_in_progress(connection, account_fingerprint):
                    return None
                if (
                    connection.execute(
                        "SELECT 1 FROM account_execution_lease WHERE account = ?",
                        (account_fingerprint,),
                    ).fetchone()
                    is not None
                ):
                    return None
                connection.execute(
                    "INSERT INTO account_execution_lease(account, token, owner_pid) "
                    "VALUES (?, ?, ?)",
                    (account_fingerprint, token, os.getpid()),
                )
            return token
        except sqlite3.Error as error:
            raise RuntimeError("Local confirmation state is unavailable.") from error

    def release_execution_lease(self, account_fingerprint: str, token: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM account_execution_lease WHERE account = ? AND token = ?",
                    (account_fingerprint, token),
                )
        except sqlite3.Error as error:
            raise RuntimeError("Local confirmation state is unavailable.") from error

    def consume_confirmation(
        self, token: str, *, account_fingerprint: str, now: datetime
    ) -> AnalysisConfirmation | None:
        row = self._consume("confirmation", token, account_fingerprint, now)
        if row is None or row[6] is None:
            return None
        return AnalysisConfirmation(
            *row[:6], input_hash=str(row[6]), expires_at=datetime.fromisoformat(row[7])
        )

    def _save(
        self, kind: str, value: AnalysisPreview | AnalysisConfirmation, *, input_hash: str | None
    ) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = _token_hash(token)
        candidates = json.dumps(
            [
                [
                    candidate.thread_id,
                    candidate.latest_message_id,
                    candidate.latest_message_at,
                    candidate.filter_hash,
                ]
                for candidate in value.candidates
            ],
            separators=(",", ":"),
        )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if self._deletion_in_progress(connection, value.account_fingerprint):
                    raise RuntimeError("Local confirmation state is unavailable.")
                connection.execute(
                    "DELETE FROM analysis_confirmation WHERE expires_at <= ?",
                    (datetime.now(value.expires_at.tzinfo).isoformat(),),
                )
                connection.execute(
                    "INSERT INTO analysis_confirmation("
                    "token_hash, kind, account, operation, query, "
                    "filter_hash, candidates_json, snapshot_hash, provider, input_hash, "
                    "expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        token_hash,
                        kind,
                        value.account_fingerprint,
                        value.operation,
                        "",
                        value.filter_hash,
                        candidates,
                        value.snapshot_hash,
                        value.provider,
                        input_hash,
                        value.expires_at.isoformat(),
                    ),
                )
            return token
        except sqlite3.Error as error:
            raise RuntimeError("Local confirmation state is unavailable.") from error

    def _consume(
        self, kind: str, token: str, account: str, now: datetime
    ) -> tuple[str, str, str, str, tuple[ThreadCandidate, ...], str, str | None, str] | None:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if self._deletion_in_progress(connection, account):
                    return None
                row = connection.execute(
                    "SELECT operation, query, filter_hash, candidates_json, snapshot_hash, "
                    "provider, "
                    "input_hash, "
                    "expires_at "
                    "FROM analysis_confirmation WHERE token_hash = ? AND kind = ? AND account = ? "
                    "AND consumed_at IS NULL AND expires_at > ?",
                    (_token_hash(token), kind, account, now.isoformat()),
                ).fetchone()
                if row is None:
                    return None
                candidates = _decode_candidates(account, str(row[3]))
                if snapshot_hash(candidates) != str(row[4]) or any(
                    candidate.filter_hash != str(row[2]) for candidate in candidates
                ):
                    return None
                if (
                    connection.execute(
                        "UPDATE analysis_confirmation SET consumed_at = ? WHERE token_hash = ? "
                        "AND consumed_at IS NULL",
                        (now.isoformat(), _token_hash(token)),
                    ).rowcount
                    != 1
                ):
                    return None
        except sqlite3.Error as error:
            raise RuntimeError("Local confirmation state is unavailable.") from error
        return (
            account,
            str(row[0]),
            str(row[1]),
            str(row[2]),
            candidates,
            str(row[5]),
            row[6],
            str(row[7]),
        )

    @staticmethod
    def _deletion_in_progress(connection: sqlite3.Connection, account: str) -> bool:
        if (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'account_deletion_gate'"
            ).fetchone()
            is None
        ):
            return False
        return (
            connection.execute(
                "SELECT 1 FROM account_deletion_gate WHERE account = ?", (account,)
            ).fetchone()
            is not None
        )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_candidates(account: str, value: str) -> tuple[ThreadCandidate, ...]:
    raw = json.loads(value)
    if not isinstance(raw, list):
        raise ValueError("Confirmation snapshot is invalid.")
    candidates: list[ThreadCandidate] = []
    for item in raw:
        if (
            not isinstance(item, list)
            or len(item) != 4
            or any(not isinstance(field, str) for field in item)
        ):
            raise ValueError("Confirmation snapshot is invalid.")
        candidates.append(ThreadCandidate(account, item[0], item[1], item[2], item[3]))
    return tuple(candidates)
