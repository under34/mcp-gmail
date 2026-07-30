from __future__ import annotations

import json

from anthropic import (
    Anthropic,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

from gmail_mcp.application.thread_summary import (
    SummaryProviderAuthenticationError,
    SummaryProviderUnavailableError,
)
from gmail_mcp.domain.thread_summary import ThreadSummary, thread_summary_from_payload


class ClaudeSummaryProviderAdapter:
    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def summarize(self, *, account_fingerprint: str, thread_id: str, text: str) -> ThreadSummary:
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system="Return JSON: summary, priority, actions; max 3 sentences.",
                messages=[{"role": "user", "content": text}],
            )
        except (AuthenticationError, PermissionDeniedError, RateLimitError) as error:
            raise SummaryProviderAuthenticationError from error
        except BadRequestError as error:
            if "credit balance is too low" in str(error).lower():
                raise SummaryProviderUnavailableError from error
            raise
        if not response.content or not getattr(response.content[0], "text", None):
            raise ValueError("Provider returned an empty summary.")
        return thread_summary_from_payload(
            json.loads(response.content[0].text),
            account_fingerprint=account_fingerprint,
            thread_id=thread_id,
            provider="claude",
        )
