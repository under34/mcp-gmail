from __future__ import annotations

import pytest

from gmail_mcp.domain.thread_summary import ThreadSummary, thread_summary_from_payload


def test_thread_summary_is_validated_and_has_a_gmail_source_link() -> None:
    summary = ThreadSummary("account", "thread", "First. Second.", "wysoki", (), "openai")

    assert summary.source_link.endswith("/thread")
    assert summary.actions == ()


def test_thread_summary_rejects_more_than_three_sentences() -> None:
    with pytest.raises(ValueError, match="three"):
        ThreadSummary("account", "thread", "One. Two. Three. Four.", "niski", (), "claude")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("schema_version", 2, "schema"), ("status", "failed", "complete")],
)
def test_thread_summary_rejects_unsupported_schema_or_status(field, value, message) -> None:
    values = {field: value}

    with pytest.raises(ValueError, match=message):
        ThreadSummary("account", "thread", "Krótko.", "niski", (), "openai", **values)


def test_thread_summary_requires_an_explicit_actions_tuple() -> None:
    with pytest.raises(ValueError, match="tuple"):
        ThreadSummary("account", "thread", "Krótko.", "niski", [], "openai")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": None, "priority": "niski", "actions": []},
        {"summary": "Krótko.", "priority": "niski"},
        {"summary": "Krótko.", "priority": "niski", "actions": "zadzwoń"},
        {"summary": "Krótko.", "priority": "niski", "actions": [], "extra": True},
    ],
)
def test_provider_payload_requires_the_exact_schema(payload) -> None:
    with pytest.raises(ValueError, match="schema"):
        thread_summary_from_payload(
            payload, account_fingerprint="account", thread_id="thread", provider="openai"
        )


def test_thread_summary_rejects_punctuation_only_summary() -> None:
    with pytest.raises(ValueError, match="three"):
        ThreadSummary("account", "thread", "...", "niski", (), "openai")
