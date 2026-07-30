import pytest

from gmail_mcp.bootstrap.paths import get_app_paths
from gmail_mcp.bootstrap.settings import ConfigurationError, Settings
from gmail_mcp.bootstrap.summary_provider import (
    create_comparison_providers,
    create_summary_provider,
)


def test_composition_uses_selected_provider_without_fallback(tmp_path) -> None:
    settings = Settings("claude", "openai-key", "claude-key", None, get_app_paths(tmp_path))

    assert create_summary_provider(settings).__class__.__name__ == "ClaudeSummaryProviderAdapter"


def test_comparison_requires_both_explicit_provider_keys(tmp_path) -> None:
    settings = Settings("openai", "openai-key", None, None, get_app_paths(tmp_path))

    with pytest.raises(ConfigurationError, match="Both AI providers"):
        create_comparison_providers(settings)


def test_comparison_rejects_a_whitespace_only_provider_key(tmp_path) -> None:
    settings = Settings("openai", "openai-key", "   ", None, get_app_paths(tmp_path))

    with pytest.raises(ConfigurationError, match="Both AI providers"):
        create_comparison_providers(settings)
