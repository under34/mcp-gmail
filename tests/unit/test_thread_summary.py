from __future__ import annotations

import pytest

from gmail_mcp.domain.thread_summary import ThreadSummary


def test_thread_summary_is_validated_and_has_a_gmail_source_link() -> None:
    summary = ThreadSummary("account", "thread", "First. Second.", "wysoki", (), "openai")

    assert summary.source_link.endswith("/thread")
    assert summary.actions == ()


def test_thread_summary_rejects_more_than_three_sentences() -> None:
    with pytest.raises(ValueError, match="three"):
        ThreadSummary("account", "thread", "One. Two. Three. Four.", "niski", (), "claude")
