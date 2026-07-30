from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from mcp.server.fastmcp import FastMCP


class SummarizeGmailPort(Protocol):
    def preview(self, query: str | None = None) -> dict[str, object]: ...
    def confirm(self, preview_token: str) -> dict[str, object]: ...
    def execute(self, confirmation_token: str | None) -> dict[str, object]: ...


class CompareSummariesPort(Protocol):
    def preview(self, thread_id: str | None) -> dict[str, object]: ...
    def confirm(self, preview_token: str) -> dict[str, object]: ...
    def execute(self, confirmation_token: str | None) -> dict[str, object]: ...


def create_server(
    get_digest: Callable[[str], dict[str, object]],
    account_fingerprint: Callable[[], str],
    summarize: SummarizeGmailPort | None = None,
    compare: CompareSummariesPort | None = None,
) -> FastMCP:
    server = FastMCP("Gmail MCP", json_response=True)

    @server.tool()
    def get_daily_digest() -> dict[str, object]:
        """Return the latest local daily Gmail digest for the active account."""
        try:
            account = account_fingerprint()
            result = get_digest(account)
            if account_fingerprint() != account:
                return _failed("Gmail account changed during digest lookup.", "Retry later.")
            return result
        except Exception:
            return _failed("Gmail account is unavailable.", "Reconnect Gmail and retry.")

    @server.tool()
    def summarize_gmail(
        query: str | None = None,
        preview_token: str | None = None,
        confirm: bool = False,
        confirmation_token: str | None = None,
    ) -> dict[str, object]:
        """Preview, confirm, then summarize a one-off Gmail scope."""
        if summarize is None:
            return _failed(
                "Ad-hoc analysis is not available yet.", "Use a later version of this tool."
            )
        try:
            if confirmation_token is not None and not confirmation_token:
                return _failed(
                    "A valid confirmation token is required.",
                    "Refresh the preview and confirm it again.",
                )
            if confirmation_token is not None and not any((query, preview_token, confirm)):
                return summarize.execute(confirmation_token)
            if preview_token and confirm and not any((query, confirmation_token)):
                return summarize.confirm(preview_token)
            if not any((preview_token, confirmation_token, confirm)):
                return summarize.preview(query)
        except Exception:
            return _failed("Ad-hoc analysis is unavailable.", "Refresh the preview and retry.")
        return _failed("Invalid confirmation request.", "Refresh the preview and confirm it again.")

    @server.tool()
    def compare_summaries(
        thread_id: str | None = None,
        preview_token: str | None = None,
        confirm: bool = False,
        confirmation_token: str | None = None,
    ) -> dict[str, object]:
        """Preview, confirm, then compare OpenAI and Claude for one filtered thread."""
        if compare is None:
            return _failed("Summary comparison is not available yet.", "Configure both providers.")
        try:
            if preview_token is not None and not preview_token:
                return _failed(
                    "A valid preview token is required.",
                    "Refresh the preview and confirm it again.",
                )
            if confirmation_token is not None and not confirmation_token:
                return _failed(
                    "A valid confirmation token is required.",
                    "Refresh the preview and confirm it again.",
                )
            if confirmation_token is not None and not any((thread_id, preview_token, confirm)):
                return compare.execute(confirmation_token)
            if preview_token and confirm and not any((thread_id, confirmation_token)):
                return compare.confirm(preview_token)
            if not any((preview_token, confirmation_token, confirm)):
                return compare.preview(thread_id)
        except Exception:
            return _failed("Summary comparison is unavailable.", "Refresh the preview and retry.")
        return _failed("Invalid comparison request.", "Refresh the preview and confirm it again.")

    return server


def _failed(reason: str, next_action: str) -> dict[str, object]:
    return {"status": "failed", "data": None, "reason": reason, "next_action": next_action}
