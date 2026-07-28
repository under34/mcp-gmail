from __future__ import annotations

import json

from anthropic import Anthropic

from gmail_mcp.domain.thread_summary import ThreadSummary


class ClaudeSummaryProviderAdapter:
    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        response = self._client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="Return JSON: summary, priority, actions; max 3 sentences.",
            messages=[{"role": "user", "content": text}],
        )
        if not response.content or not getattr(response.content[0], "text", None):
            raise ValueError("Provider returned an empty summary.")
        value = json.loads(response.content[0].text)
        return ThreadSummary(account_fingerprint, thread_id, str(value["summary"]), str(value["priority"]), tuple(str(item) for item in value.get("actions", [])), "claude")  # noqa: E501
