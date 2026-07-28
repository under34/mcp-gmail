from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from gmail_mcp.domain.gmail_filter import GmailFilter


class ActiveFilterRepositoryAdapter:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    @staticmethod
    def _fingerprint(account_email: str) -> str:
        return hashlib.sha256(account_email.strip().lower().encode()).hexdigest()

    def _path(self, account_email: str) -> Path:
        return self._directory / f"{self._fingerprint(account_email)}.json"

    def load(self, account_email: str) -> GmailFilter | None:
        path = self._path(account_email)
        if path.is_symlink() or not path.is_file():
            if not path.exists() and not path.is_symlink():
                return None
            raise ValueError("Active Gmail filter path is unsafe.")
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if (
                state.get("version") != 1
                or state.get("account_fingerprint") != self._fingerprint(account_email)
            ):
                raise ValueError("Active Gmail filter state is unsupported.")
            return GmailFilter(str(state["query"]))
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Active Gmail filter state is invalid.") from error

    def save(self, account_email: str, filter_: GmailFilter) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        if self._directory.is_symlink():
            raise ValueError("Active Gmail filter directory is unsafe.")
        path = self._path(account_email)
        if path.is_symlink():
            raise ValueError("Active Gmail filter path is unsafe.")
        fd, temp_name = tempfile.mkstemp(dir=self._directory, prefix=".filter-", text=True)
        temp_path = Path(temp_name)
        try:
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump({"version": 1, "account_fingerprint": self._fingerprint(account_email),
                           "query": filter_.query}, file, separators=(",", ":"))
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
