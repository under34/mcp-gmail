from __future__ import annotations

import asyncio

from gmail_mcp.adapters.fastmcp_server import create_server


class FakeSummarize:
    def preview(self, query=None):
        return {
            "status": "complete",
            "data": {"phase": "preview", "query": query},
            "reason": None,
            "next_action": None,
        }

    def confirm(self, preview_token):
        return {
            "status": "complete",
            "data": {"phase": "confirmed", "token": preview_token},
            "reason": None,
            "next_action": None,
        }

    def execute(self, confirmation_token):
        return {
            "status": "complete",
            "data": {"phase": "executed", "token": confirmation_token},
            "reason": None,
            "next_action": None,
        }


class FakeCompare(FakeSummarize):
    def preview(self, thread_id=None):
        return {
            "status": "complete",
            "data": {"phase": "preview", "thread_id": thread_id},
            "reason": None,
            "next_action": None,
        }

async def _assert_tools() -> None:
    server = create_server(
        lambda account: {
            "status": "complete",
            "data": {"account": account},
            "reason": None,
            "next_action": None,
        },
        lambda: "account",
    )

    assert {tool.name for tool in await server.list_tools()} == {
        "get_daily_digest",
        "summarize_gmail",
        "compare_summaries",
    }
    assert (await server.call_tool("get_daily_digest", {}))[1]["data"] == {"account": "account"}
    assert (await server.call_tool("summarize_gmail", {}))[1]["status"] == "failed"


def test_fastmcp_server_exposes_exactly_three_safe_tools() -> None:
    asyncio.run(_assert_tools())


async def _assert_confirmed_protocol() -> None:
    server = create_server(lambda _: {}, lambda: "account", FakeSummarize())

    assert (await server.call_tool("summarize_gmail", {"query": "label:work"}))[1]["data"] == {
        "phase": "preview",
        "query": "label:work",
    }
    assert (
        await server.call_tool("summarize_gmail", {"preview_token": "preview", "confirm": True})
    )[1]["data"] == {"phase": "confirmed", "token": "preview"}
    assert (await server.call_tool("summarize_gmail", {"confirmation_token": "confirmed"}))[1][
        "data"
    ] == {"phase": "executed", "token": "confirmed"}
    assert (await server.call_tool("summarize_gmail", {"confirmation_token": ""}))[1][
        "status"
    ] == "failed"


def test_fastmcp_server_routes_three_phase_confirmed_analysis() -> None:
    asyncio.run(_assert_confirmed_protocol())


async def _assert_comparison_protocol() -> None:
    server = create_server(lambda _: {}, lambda: "account", FakeSummarize(), FakeCompare())

    assert (await server.call_tool("compare_summaries", {"thread_id": "thread"}))[1]["data"] == {
        "phase": "preview",
        "thread_id": "thread",
    }
    assert (
        await server.call_tool("compare_summaries", {"preview_token": "preview", "confirm": True})
    )[1]["data"] == {"phase": "confirmed", "token": "preview"}
    assert (await server.call_tool("compare_summaries", {"confirmation_token": "confirmed"}))[1][
        "data"
    ] == {"phase": "executed", "token": "confirmed"}
    assert (await server.call_tool("compare_summaries", {"confirmation_token": ""}))[1][
        "status"
    ] == "failed"


def test_fastmcp_server_routes_three_phase_comparison() -> None:
    asyncio.run(_assert_comparison_protocol())
