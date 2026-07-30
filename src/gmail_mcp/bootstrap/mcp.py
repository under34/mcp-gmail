from __future__ import annotations

import hashlib

from gmail_mcp.adapters.active_filter_repository import ActiveFilterRepositoryAdapter
from gmail_mcp.adapters.fastmcp_server import create_server
from gmail_mcp.adapters.gmail_oauth import GmailOAuthAdapter
from gmail_mcp.adapters.sqlite_analysis_state import SqliteAnalysisStateAdapter
from gmail_mcp.adapters.sqlite_confirmation import SqliteConfirmationAdapter
from gmail_mcp.application.analysis_state import FinishAnalysis, PlanAnalysis
from gmail_mcp.application.confirmed_analysis import ConfirmedAdHocAnalysis
from gmail_mcp.application.digest_read import GetDailyDigest
from gmail_mcp.application.thread_summary import SummarizeAnalysisRun
from gmail_mcp.bootstrap.settings import (
    ConfigurationError,
    load_gmail_settings,
    load_settings,
)
from gmail_mcp.bootstrap.summary_provider import create_summary_provider


class _UnavailableAdHocAnalysis:
    def preview(self, query: str | None = None) -> dict[str, object]:
        return self._failed()

    def confirm(self, preview_token: str) -> dict[str, object]:
        return self._failed()

    def execute(self, confirmation_token: str | None) -> dict[str, object]:
        return self._failed()

    @staticmethod
    def _failed() -> dict[str, object]:
        return {
            "status": "failed",
            "data": None,
            "reason": "The selected AI provider is not configured.",
            "next_action": "Configure the selected provider and refresh the preview.",
        }


def main() -> int:
    gmail_settings = load_gmail_settings(require_credentials=False)
    gmail = GmailOAuthAdapter(gmail_settings.credentials_path, gmail_settings.paths.oauth_token)
    state = SqliteAnalysisStateAdapter(gmail_settings.paths.sqlite)
    reader = GetDailyDigest(state)
    try:
        settings = load_settings()
        ad_hoc = ConfirmedAdHocAnalysis(
            gmail,
            ActiveFilterRepositoryAdapter(settings.paths.filters),
            SqliteConfirmationAdapter(settings.paths.sqlite),
            PlanAnalysis(state),
            FinishAnalysis(state),
            SummarizeAnalysisRun(
                gmail, create_summary_provider(settings), state, FinishAnalysis(state)
            ),
            state,
            provider=settings.ai_provider,
        )
    except ConfigurationError:
        ad_hoc = _UnavailableAdHocAnalysis()

    def account_fingerprint() -> str:
        return hashlib.sha256(gmail.current_account_email().strip().lower().encode()).hexdigest()

    create_server(reader.execute, account_fingerprint, ad_hoc).run(transport="stdio")
    return 0
