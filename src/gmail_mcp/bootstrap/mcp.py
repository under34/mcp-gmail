from __future__ import annotations

import hashlib

from gmail_mcp.adapters.fastmcp_server import create_server
from gmail_mcp.adapters.gmail_oauth import GmailOAuthAdapter
from gmail_mcp.adapters.sqlite_analysis_state import SqliteAnalysisStateAdapter
from gmail_mcp.application.digest_read import GetDailyDigest
from gmail_mcp.bootstrap.settings import load_gmail_settings


def main() -> int:
    settings = load_gmail_settings(require_credentials=False)
    gmail = GmailOAuthAdapter(settings.credentials_path, settings.paths.oauth_token)
    reader = GetDailyDigest(SqliteAnalysisStateAdapter(settings.paths.sqlite))

    def account_fingerprint() -> str:
        return hashlib.sha256(gmail.current_account_email().strip().lower().encode()).hexdigest()

    create_server(reader.execute, account_fingerprint).run(transport="stdio")
    return 0
