from __future__ import annotations

from gmail_mcp.adapters.claude_summary import ClaudeSummaryProviderAdapter
from gmail_mcp.adapters.openai_summary import OpenAISummaryProviderAdapter
from gmail_mcp.application.thread_summary import SummaryProviderPort
from gmail_mcp.bootstrap.settings import ConfigurationError, Settings


def create_summary_provider(settings: Settings) -> SummaryProviderPort:
    """Compose exactly the configured provider; never fall back to another one."""
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required for the selected AI_PROVIDER.")
        return OpenAISummaryProviderAdapter(settings.openai_api_key)
    if not settings.anthropic_api_key:
        raise ConfigurationError("ANTHROPIC_API_KEY is required for the selected AI_PROVIDER.")
    return ClaudeSummaryProviderAdapter(settings.anthropic_api_key)


def create_comparison_providers(settings: Settings) -> dict[str, SummaryProviderPort]:
    """Compose both concrete providers for an explicitly confirmed comparison."""
    if not settings.openai_api_key or not settings.anthropic_api_key:
        raise ConfigurationError("Both AI providers must be configured for comparison.")
    return {
        "openai": OpenAISummaryProviderAdapter(settings.openai_api_key),
        "claude": ClaudeSummaryProviderAdapter(settings.anthropic_api_key),
    }
