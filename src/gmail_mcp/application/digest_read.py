from __future__ import annotations

from typing import Protocol

from gmail_mcp.domain.digest import Digest


class LatestDigestPort(Protocol):
    def latest_digest(self, account_fingerprint: str) -> Digest | None: ...


class GetDailyDigest:
    def __init__(self, repository: LatestDigestPort) -> None:
        self._repository = repository

    def execute(self, account_fingerprint: str) -> dict[str, object]:
        try:
            digest = self._repository.latest_digest(account_fingerprint)
        except Exception:
            return _failed("Local digest state is unavailable.", "Retry later.")
        if digest is None:
            return _failed("No daily digest is available.", "Run the daily digest first.")
        data = {
            "generated_at": digest.generated_at,
            "covered_from": digest.covered_from,
            "covered_to": digest.covered_to,
            "matching_thread_count": digest.matching_thread_count,
            "provider": digest.provider,
            "items": [
                {
                    "thread_id": item.thread_id,
                    "source_link": item.summary.source_link,
                    "summary": item.summary.summary,
                    "priority": item.summary.priority,
                    "actions": list(item.summary.actions),
                    "provider": item.summary.provider,
                    "inclusion_reason": item.inclusion_reason,
                    "disclaimer": item.summary.disclaimer,
                }
                for item in digest.items
            ],
        }
        return {
            "status": digest.status,
            "data": data if digest.status != "failed" else None,
            "reason": digest.reason,
            "next_action": digest.next_action,
        }


def _failed(reason: str, next_action: str) -> dict[str, object]:
    return {"status": "failed", "data": None, "reason": reason, "next_action": next_action}
