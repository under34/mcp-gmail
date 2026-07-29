from gmail_mcp.bootstrap.paths import get_app_paths
from gmail_mcp.bootstrap.settings import Settings
from gmail_mcp.bootstrap.summary_provider import create_summary_provider


def test_composition_uses_selected_provider_without_fallback(tmp_path) -> None:
    settings = Settings("claude", "openai-key", "claude-key", None, get_app_paths(tmp_path))

    assert create_summary_provider(settings).__class__.__name__ == "ClaudeSummaryProviderAdapter"
