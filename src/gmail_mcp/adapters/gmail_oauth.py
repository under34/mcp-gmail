from __future__ import annotations

import os
import tempfile
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_mcp.domain.gmail_connection import ConnectionResult

GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)
RECONNECT_ACTION = "Run gmail-mcp connect-gmail."


class GmailOAuthAdapter:
    def __init__(self, credentials_path: Path | None, token_path: Path) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path

    def connect(self) -> ConnectionResult:
        try:
            credentials = self._load_credentials()
        except Exception:
            self._delete_invalid_token()
            credentials = None
        try:
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    try:
                        credentials.refresh(Request())
                    except Exception:
                        self._delete_invalid_token()
                        return ConnectionResult.failed(
                            "Gmail authorization failed.", RECONNECT_ACTION
                        )
                else:
                    credentials = self._run_local_flow()
                self._write_token(credentials)
            return ConnectionResult.complete(self._profile_email(credentials))
        except HttpError as error:
            if getattr(error.resp, "status", None) in {401, 403}:
                self._delete_invalid_token()
            return ConnectionResult.failed("Gmail authorization failed.", RECONNECT_ACTION)
        except Exception:
            return ConnectionResult.failed("Gmail authorization failed.", RECONNECT_ACTION)

    def require_connection(self) -> ConnectionResult:
        if self._token_path.is_symlink() or not self._token_path.is_file():
            return ConnectionResult.failed("Gmail authorization is unavailable.", RECONNECT_ACTION)
        try:
            credentials = self._load_credentials()
            if not credentials:
                return ConnectionResult.failed(
                    "Gmail authorization is unavailable.", RECONNECT_ACTION
                )
            if not credentials.valid:
                if not (credentials.expired and credentials.refresh_token):
                    return ConnectionResult.failed(
                        "Gmail authorization is unavailable.", RECONNECT_ACTION
                    )
                credentials.refresh(Request())
                self._write_token(credentials)
            return ConnectionResult.complete(self._profile_email(credentials))
        except Exception:
            return ConnectionResult.failed("Gmail authorization failed.", RECONNECT_ACTION)

    def disconnect(self) -> ConnectionResult:
        if self._token_path.is_symlink():
            return ConnectionResult.failed("Gmail token path is unsafe.", RECONNECT_ACTION)
        if self._token_path.exists() and not self._token_path.is_file():
            return ConnectionResult.failed("Gmail token path is unsafe.", RECONNECT_ACTION)
        try:
            self._token_path.unlink(missing_ok=True)
            return ConnectionResult.complete()
        except OSError:
            return ConnectionResult.failed("Gmail token could not be removed.", RECONNECT_ACTION)

    def _load_credentials(self) -> Credentials | None:
        if self._token_path.is_symlink() or not self._token_path.is_file():
            return None
        return Credentials.from_authorized_user_file(str(self._token_path), GMAIL_SCOPES)

    def _run_local_flow(self) -> Credentials:
        if self._credentials_path is None:
            raise ValueError("Gmail credentials are unavailable.")
        flow = InstalledAppFlow.from_client_secrets_file(str(self._credentials_path), GMAIL_SCOPES)
        return flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)

    def _profile_email(self, credentials: Credentials) -> str:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return str(service.users().getProfile(userId="me").execute()["emailAddress"])

    def preview_threads(self, query: str) -> tuple[str, int]:
        connection = self.require_connection()
        if connection.status != "complete":
            raise ValueError("Gmail authorization is unavailable.")
        credentials = self._load_credentials()
        if credentials is None:
            raise ValueError("Gmail authorization is unavailable.")
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        count = 0
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            request = service.users().threads().list(userId="me", q=query, pageToken=page_token)
            response = request.execute()
            count += len(response.get("threads", []))
            next_token = response.get("nextPageToken")
            if not next_token:
                return connection.email_address or self._profile_email(credentials), count
            if next_token in seen_tokens:
                raise ValueError("Gmail pagination failed.")
            seen_tokens.add(next_token)
            page_token = str(next_token)

    def current_account_email(self) -> str:
        result = self.require_connection()
        if result.status != "complete" or not result.email_address:
            raise ValueError("Gmail authorization is unavailable.")
        return result.email_address

    def _write_token(self, credentials: Credentials) -> None:
        if self._token_path.is_symlink():
            raise ValueError("Token path is unsafe.")
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            dir=self._token_path.parent, prefix=".token-", text=True
        )
        temporary_path = Path(name)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as token_file:
                token_file.write(credentials.to_json())
            os.replace(temporary_path, self._token_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _delete_invalid_token(self) -> None:
        if not self._token_path.is_symlink():
            try:
                self._token_path.unlink(missing_ok=True)
            except OSError:
                pass
