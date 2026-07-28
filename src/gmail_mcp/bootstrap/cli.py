from __future__ import annotations

import argparse

from gmail_mcp.adapters.active_filter_repository import ActiveFilterRepositoryAdapter
from gmail_mcp.adapters.gmail_oauth import GmailOAuthAdapter
from gmail_mcp.application.gmail_connection import (
    ConnectGmailAccount,
    DisconnectGmailAccount,
    RequireGmailConnection,
)
from gmail_mcp.application.gmail_filter import PreviewGmailFilter, SaveActiveGmailFilter
from gmail_mcp.bootstrap.settings import (
    ConfigurationError,
    load_gmail_settings,
    load_provider_status,
)
from gmail_mcp.domain.gmail_filter import DEFAULT_GMAIL_QUERY


def main() -> int:
    parser = argparse.ArgumentParser(prog="gmail-mcp")
    parser.add_argument(
        "command",
        choices=(
            "connect-gmail", "disconnect-gmail", "gmail-status", "preview-gmail-filter",
            "set-gmail-filter", "gmail-filter-status", "ai-provider-status",
        ),
    )
    parser.add_argument("--query")
    parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args()
    command = arguments.command
    if command == "ai-provider-status":
        try:
            status = load_provider_status()
        except ConfigurationError as error:
            print(f"failed: {error}")
            return 1
        available = {"openai": status.openai_available, "claude": status.claude_available}
        if not available[status.selected]:
            print(f"failed: {status.selected} is not configured. Add its API key.")
            return 1
        print(
            f"complete: selected={status.selected} openai={available['openai']} "
            f"claude={available['claude']}"
        )
        return 0
    try:
        settings = load_gmail_settings(require_credentials=command == "connect-gmail")
    except ConfigurationError as error:
        print(f"failed: {error}")
        return 1
    adapter = GmailOAuthAdapter(settings.credentials_path, settings.paths.oauth_token)
    if command in {"preview-gmail-filter", "set-gmail-filter", "gmail-filter-status"}:
        repository = ActiveFilterRepositoryAdapter(settings.paths.filters)
        if command == "gmail-filter-status":
            try:
                filter_ = repository.load(adapter.current_account_email())
                print(filter_.query if filter_ else DEFAULT_GMAIL_QUERY)
                return 0
            except Exception:
                print("failed: Gmail filter status is unavailable. Run gmail-mcp connect-gmail.")
                return 1
        preview = PreviewGmailFilter(adapter)
        if command == "preview-gmail-filter":
            result = preview.execute(arguments.query)
        else:
            result = SaveActiveGmailFilter(preview, repository).execute(
                arguments.query, confirmed=arguments.confirm
            )
        if result.status == "complete":
            print(
                f"complete: query={result.filter.query} threads={result.matching_thread_count} "
                f"persisted={result.persisted}"
            )
            return 0
        print(f"failed: {result.reason} {result.next_action}")
        return 1
    actions = {
        "connect-gmail": ConnectGmailAccount(adapter).execute,
        "disconnect-gmail": DisconnectGmailAccount(adapter).execute,
        "gmail-status": RequireGmailConnection(adapter).execute,
    }
    result = actions[command]()
    if result.status == "complete":
        print(result.email_address or "complete")
        return 0
    print(f"failed: {result.reason} {result.next_action}")
    return 1
