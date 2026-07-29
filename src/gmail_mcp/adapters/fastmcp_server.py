from __future__ import annotations

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP


def create_server(
    get_digest: Callable[[str], dict[str, object]], account_fingerprint: Callable[[], str]
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
    def summarize_gmail() -> dict[str, object]:
        """Reserved for the confirmed ad-hoc analysis workflow."""
        return _failed("Ad-hoc analysis is not available yet.", "Use a later version of this tool.")

    @server.tool()
    def compare_summaries() -> dict[str, object]:
        """Reserved for the confirmed provider comparison workflow."""
        return _failed(
            "Summary comparison is not available yet.", "Use a later version of this tool."
        )

    return server


def _failed(reason: str, next_action: str) -> dict[str, object]:
    return {"status": "failed", "data": None, "reason": reason, "next_action": next_action}
