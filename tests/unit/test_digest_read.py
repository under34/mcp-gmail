from __future__ import annotations

from dataclasses import dataclass

from gmail_mcp.application.digest_read import GetDailyDigest
from gmail_mcp.domain.digest import Digest, DigestItem
from gmail_mcp.domain.thread_summary import ThreadSummary


@dataclass
class Repository:
    digest: Digest | None

    def latest_digest(self, account_fingerprint: str) -> Digest | None:
        assert account_fingerprint == "account"
        return self.digest


def test_get_daily_digest_serializes_persisted_item_metadata() -> None:
    summary = ThreadSummary("account", "thread", "Krótko.", "wysoki", ("Odpowiedz.",), "openai")
    digest = Digest(
        "run", "account", "complete", "now", "from", "to", 1,
        (DigestItem(summary, "new_message"),), provider="openai"
    )

    result = GetDailyDigest(Repository(digest)).execute("account")

    assert result["status"] == "complete"
    assert result["data"]["items"][0]["thread_id"] == "thread"  # type: ignore[index]
    assert result["reason"] is None


def test_get_daily_digest_is_safe_when_missing() -> None:
    result = GetDailyDigest(Repository(None)).execute("account")

    assert result == {
        "status": "failed", "data": None, "reason": "No daily digest is available.",
        "next_action": "Run the daily digest first.",
    }
