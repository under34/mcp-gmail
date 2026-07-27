from __future__ import annotations

import argparse

from gmail_mcp.adapters.gmail_oauth import GmailOAuthAdapter
from gmail_mcp.application.gmail_connection import (
    ConnectGmailAccount,
    DisconnectGmailAccount,
    RequireGmailConnection,
)
from gmail_mcp.bootstrap.settings import ConfigurationError, load_gmail_settings


def main() -> int:
    parser = argparse.ArgumentParser(prog="gmail-mcp")
    parser.add_argument("command", choices=("connect-gmail", "disconnect-gmail", "gmail-status"))
    command = parser.parse_args().command
    try:
        settings = load_gmail_settings(require_credentials=command == "connect-gmail")
    except ConfigurationError as error:
        print(f"failed: {error}")
        return 1
    adapter = GmailOAuthAdapter(settings.credentials_path, settings.paths.oauth_token)
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
