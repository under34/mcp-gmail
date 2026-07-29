from __future__ import annotations

import asyncio

from gmail_mcp.adapters.fastmcp_server import create_server


async def _assert_tools() -> None:
    server = create_server(
        lambda account: {"status": "complete", "data": {"account": account}, "reason": None,
                         "next_action": None},
        lambda: "account",
    )

    assert {tool.name for tool in await server.list_tools()} == {
        "get_daily_digest", "summarize_gmail", "compare_summaries"
    }
    assert (await server.call_tool("get_daily_digest", {}))[1]["data"] == {"account": "account"}
    assert (await server.call_tool("summarize_gmail", {}))[1]["status"] == "failed"


def test_fastmcp_server_exposes_exactly_three_safe_tools() -> None:
    asyncio.run(_assert_tools())
