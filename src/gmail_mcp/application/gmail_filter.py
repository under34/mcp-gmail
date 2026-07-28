from __future__ import annotations

from typing import Protocol

from gmail_mcp.domain.gmail_filter import FilterPreview, FilterResult, GmailFilter


class GmailFilterPort(Protocol):
    def preview_threads(self, query: str) -> tuple[str, int]: ...


class ActiveFilterRepositoryPort(Protocol):
    def load(self, account_email: str) -> GmailFilter | None: ...
    def save(self, account_email: str, filter_: GmailFilter) -> None: ...


class PreviewGmailFilter:
    def __init__(self, gmail: GmailFilterPort) -> None:
        self._gmail = gmail

    def execute(self, query: str | None = None) -> FilterResult:
        try:
            filter_ = GmailFilter.default() if query is None else GmailFilter(query)
            email, count = self._gmail.preview_threads(filter_.query)
            return FilterResult.complete(FilterPreview(filter_, count, email))
        except ValueError as error:
            return FilterResult.failed(str(error), "Use a non-empty Gmail search query.")
        except Exception:
            return FilterResult.failed(
                "Gmail filter preview failed.", "Run gmail-mcp connect-gmail."
            )


class SaveActiveGmailFilter:
    def __init__(self, preview: PreviewGmailFilter, repository: ActiveFilterRepositoryPort) -> None:
        self._preview = preview
        self._repository = repository

    def execute(self, query: str | None, *, confirmed: bool) -> FilterResult:
        if not confirmed:
            return FilterResult.failed("Gmail filter was not saved.", "Re-run with --confirm.")
        result = self._preview.execute(query)
        if result.status != "complete" or result.filter is None:
            return result
        try:
            self._repository.save(result.account_email or "", result.filter)
            return FilterResult(
                "complete",
                filter=result.filter,
                matching_thread_count=result.matching_thread_count,
                account_email=result.account_email,
                persisted=True,
            )
        except Exception:
            return FilterResult.failed(
                "Gmail filter could not be saved.", "Check local application data."
            )
