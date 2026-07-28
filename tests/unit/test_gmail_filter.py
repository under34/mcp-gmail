from __future__ import annotations

import os
from pathlib import Path

import pytest

from gmail_mcp.adapters.active_filter_repository import ActiveFilterRepositoryAdapter
from gmail_mcp.domain.gmail_filter import DEFAULT_GMAIL_QUERY, GmailFilter


def test_filter_strips_only_outer_whitespace() -> None:
    filter_ = GmailFilter("  from:boss@example.com \"two  words\"  ")

    assert filter_.query == 'from:boss@example.com "two  words"'


def test_filter_rejects_whitespace_only_query() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        GmailFilter(" \t ")


def test_default_filter_is_inbox_without_social_or_promotions() -> None:
    assert GmailFilter.default().query == DEFAULT_GMAIL_QUERY


def test_repository_round_trips_a_filter_per_account(tmp_path: Path) -> None:
    repository = ActiveFilterRepositoryAdapter(tmp_path / "filters")
    repository.save("Owner@example.com", GmailFilter("from:owner"))
    repository.save("other@example.com", GmailFilter("label:work"))

    assert repository.load("owner@example.com") == GmailFilter("from:owner")
    assert repository.load("other@example.com") == GmailFilter("label:work")


def test_repository_returns_none_for_missing_filter(tmp_path: Path) -> None:
    assert ActiveFilterRepositoryAdapter(tmp_path / "filters").load("owner@example.com") is None


def test_repository_rejects_invalid_or_mismatched_state(tmp_path: Path) -> None:
    repository = ActiveFilterRepositoryAdapter(tmp_path / "filters")
    path = repository._path("owner@example.com")
    path.parent.mkdir()
    path.write_text('{"version":1,"account_fingerprint":"wrong","query":"in:inbox"}')

    with pytest.raises(ValueError, match="unsupported"):
        repository.load("owner@example.com")


def test_repository_rejects_symlink_and_writes_private_file(tmp_path: Path) -> None:
    repository = ActiveFilterRepositoryAdapter(tmp_path / "filters")
    repository.save("owner@example.com", GmailFilter("in:inbox"))
    path = repository._path("owner@example.com")
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    target = tmp_path / "target.json"
    target.write_text("{}")
    path.unlink()
    path.symlink_to(target)

    with pytest.raises(ValueError, match="unsafe"):
        repository.load("owner@example.com")


def test_repository_rejects_broken_symlink(tmp_path: Path) -> None:
    repository = ActiveFilterRepositoryAdapter(tmp_path / "filters")
    path = repository._path("owner@example.com")
    path.parent.mkdir()
    path.symlink_to(tmp_path / "missing.json")

    with pytest.raises(ValueError, match="unsafe"):
        repository.load("owner@example.com")
