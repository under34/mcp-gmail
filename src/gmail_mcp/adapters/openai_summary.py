from __future__ import annotations

import json

from openai import OpenAI

from gmail_mcp.domain.thread_summary import ThreadSummary


class OpenAISummaryProviderAdapter:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key)

    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        response = self._client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Return JSON: summary, priority, actions; max 3 sentences.",
                },
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Provider returned an empty summary.")
        value = json.loads(content)
        return ThreadSummary(account_fingerprint, thread_id, str(value["summary"]), str(value["priority"]), tuple(str(item) for item in value.get("actions", [])), "openai")  # noqa: E501
