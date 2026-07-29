from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from gmail_mcp.adapters.active_filter_repository import ActiveFilterRepositoryAdapter
from gmail_mcp.adapters.gmail_oauth import GmailOAuthAdapter
from gmail_mcp.adapters.sqlite_analysis_state import SqliteAnalysisStateAdapter
from gmail_mcp.application.analysis_state import FinishAnalysis, PlanActiveFilterAnalysis
from gmail_mcp.application.digest import RunDailyDigest
from gmail_mcp.application.gmail_connection import (
    ConnectGmailAccount,
    DisconnectGmailAccount,
    RequireGmailConnection,
)
from gmail_mcp.application.gmail_filter import PreviewGmailFilter, SaveActiveGmailFilter
from gmail_mcp.application.local_data import DeleteLocalData, PurgeExpiredResults
from gmail_mcp.application.thread_summary import SummarizeAnalysisRun
from gmail_mcp.bootstrap.settings import (
    ConfigurationError,
    load_gmail_settings,
    load_provider_status,
    load_settings,
)
from gmail_mcp.bootstrap.summary_provider import create_summary_provider
from gmail_mcp.domain.digest import Digest
from gmail_mcp.domain.gmail_filter import DEFAULT_GMAIL_QUERY


def main() -> int:
    parser = argparse.ArgumentParser(prog="gmail-mcp")
    parser.add_argument(
        "command",
        choices=(
            "connect-gmail", "disconnect-gmail", "gmail-status", "preview-gmail-filter",
            "set-gmail-filter", "gmail-filter-status", "ai-provider-status",
            "run-daily-digest", "cleanup-local-data", "delete-local-data",
        ),
    )
    parser.add_argument("--query")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--include-oauth-token", action="store_true")
    arguments = parser.parse_args()
    command = arguments.command
    if command == "delete-local-data" and not arguments.confirm:
        print("failed: delete-local-data requires --confirm")
        return 1
    if command == "run-daily-digest":
        try:
            settings = load_settings()
            if arguments.scheduled and not settings.digest_schedule_enabled:
                print("complete: digest schedule is disabled")
                return 0
            if arguments.scheduled:
                timezone = (
                    ZoneInfo(settings.digest_schedule_timezone)
                    if settings.digest_schedule_timezone
                    else None
                )
                now = datetime.now(timezone)
                if (now.hour, now.minute) != (
                    settings.digest_schedule_time.hour,
                    settings.digest_schedule_time.minute,
                ):
                    print("complete: digest is not due")
                    return 0
            gmail = GmailOAuthAdapter(settings.credentials_path, settings.paths.oauth_token)
            state = SqliteAnalysisStateAdapter(settings.paths.sqlite)
            retention = PurgeExpiredResults(state).execute()
            if retention.status == "failed":
                print(f"failed: {retention.reason} {retention.next_action}")
                return 1
            filters = ActiveFilterRepositoryAdapter(settings.paths.filters)
            plan = PlanActiveFilterAnalysis(gmail, filters, state)
            summarize = SummarizeAnalysisRun(
                gmail, create_summary_provider(settings), state, FinishAnalysis(state)
            )
            digest = RunDailyDigest(plan, summarize, state, settings.ai_provider).execute()
        except ConfigurationError as error:
            try:
                fallback = load_gmail_settings(require_credentials=False)
                SqliteAnalysisStateAdapter(fallback.paths.sqlite).save_digest(
                    Digest(
                        str(uuid4()), "", "failed", datetime.now().astimezone().isoformat(),
                        None, None, 0, (), reason="Digest configuration is unavailable.",
                        next_action="Configure the selected provider and retry.",
                    )
                )
            except Exception:
                pass
            print(f"failed: {error}")
            return 1
        except Exception:
            print("failed: Daily digest is unavailable. Check Gmail and provider configuration.")
            return 1
        print(
            f"{digest.status}: threads={digest.matching_thread_count} {digest.reason or ''}".strip()
        )
        return 1 if digest.status == "failed" else 0
    if command == "cleanup-local-data":
        try:
            settings = load_gmail_settings(require_credentials=False)
            state = SqliteAnalysisStateAdapter(settings.paths.sqlite)
            result = PurgeExpiredResults(state).execute()
        except ConfigurationError as error:
            print(f"failed: {error}")
            return 1
        if result.status == "complete":
            print(
                f"complete: digests={result.deleted_digests} summaries={result.deleted_summaries}"
            )
            return 0
        print(f"failed: {result.reason} {result.next_action}")
        return 1
    if command == "delete-local-data":
        try:
            settings = load_gmail_settings(require_credentials=False)
            gmail = GmailOAuthAdapter(settings.credentials_path, settings.paths.oauth_token)
            state = SqliteAnalysisStateAdapter(settings.paths.sqlite)
            try:
                email = gmail.current_account_email().strip().lower()
                account: str | None = hashlib.sha256(email.encode()).hexdigest()
            except Exception:
                accounts = state.local_account_fingerprints()
                if len(accounts) > 1:
                    print(
                        "failed: Local account selection is unavailable. Reconnect Gmail and retry."
                    )
                    return 1
                account = accounts[0] if accounts else None
            result = DeleteLocalData(state, gmail).execute(
                account, include_oauth_token=arguments.include_oauth_token
            )
        except ConfigurationError as error:
            print(f"failed: {error}")
            return 1
        except Exception:
            print("failed: Local data deletion is unavailable. Retry later.")
            return 1
        if result.status == "complete":
            print(
                "complete: "
                f"digests={result.deleted_digests} summaries={result.deleted_summaries} "
                f"runs={result.deleted_runs}"
            )
            return 0
        print(f"{result.status}: {result.reason} {result.next_action}")
        return 1
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
