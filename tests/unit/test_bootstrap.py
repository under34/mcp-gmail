from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

import pytest

from gmail_mcp.bootstrap.logging import SecretRedactingFilter
from gmail_mcp.bootstrap.paths import get_app_paths, restrict_file_permissions
from gmail_mcp.bootstrap.settings import (
    ConfigurationError,
    load_gmail_settings,
    load_provider_status,
    load_settings,
)


def test_load_settings_uses_environment_and_defaults_to_openai(tmp_path: Path) -> None:
    settings = load_settings(
        environ={"OPENAI_API_KEY": "openai-test-secret"},
        env_file=tmp_path / "missing.env",
        data_dir=tmp_path / "data",
    )

    assert settings.ai_provider == "openai"
    assert settings.openai_api_key == "openai-test-secret"
    assert settings.anthropic_api_key is None
    assert settings.digest_schedule_enabled is True
    assert settings.digest_schedule_time.isoformat() == "08:00:00"


def test_digest_schedule_settings_allow_a_custom_time_or_disablement(tmp_path: Path) -> None:
    settings = load_settings(
        environ={
            "OPENAI_API_KEY": "openai-test-secret",
            "DIGEST_SCHEDULE_ENABLED": "false",
            "DIGEST_SCHEDULE_TIME": "06:30",
        },
        env_file=tmp_path / "missing.env",
        data_dir=tmp_path / "data",
    )

    assert settings.digest_schedule_enabled is False
    assert settings.digest_schedule_time.isoformat() == "06:30:00"


def test_local_dotenv_is_used_when_process_environment_has_no_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    settings = load_settings(environ={}, env_file=env_file, data_dir=tmp_path / "data")

    assert settings.openai_api_key == "from-dotenv"


def test_environment_takes_precedence_over_local_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    settings = load_settings(
        environ={"OPENAI_API_KEY": "from-environment"},
        env_file=env_file,
        data_dir=tmp_path / "data",
    )

    assert settings.openai_api_key == "from-environment"


def test_selected_provider_requires_only_its_own_key(tmp_path: Path) -> None:
    settings = load_settings(
        environ={"AI_PROVIDER": "claude", "ANTHROPIC_API_KEY": "claude-test-secret"},
        env_file=tmp_path / "missing.env",
        data_dir=tmp_path / "data",
    )

    assert settings.ai_provider == "claude"
    assert settings.anthropic_api_key == "claude-test-secret"
    assert settings.openai_api_key is None


def test_missing_selected_provider_key_is_safe(tmp_path: Path) -> None:
    secret = "never-show-this-value"

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(
            environ={"AI_PROVIDER": "openai", "UNRELATED_SECRET": secret},
            env_file=tmp_path / "missing.env",
            data_dir=tmp_path / "data",
        )

    assert "OPENAI_API_KEY" in str(exc_info.value)
    assert secret not in str(exc_info.value)


def test_whitespace_selected_provider_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        load_settings(
            environ={"OPENAI_API_KEY": "   "},
            env_file=tmp_path / "missing.env",
            data_dir=tmp_path / "data",
        )


def test_invalid_provider_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="AI_PROVIDER"):
        load_settings(
            environ={"AI_PROVIDER": "other"},
            env_file=tmp_path / "missing.env",
            data_dir=tmp_path / "data",
        )


def test_data_directory_inside_checkout_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = Path.cwd()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigurationError, match="GMAIL_MCP_DATA_DIR"):
        load_settings(
            environ={
                "OPENAI_API_KEY": "openai-test-secret",
                "GMAIL_MCP_DATA_DIR": str(repository_root / "data"),
            },
            env_file=tmp_path / "missing.env",
        )


def test_app_paths_are_created_outside_repository(tmp_path: Path) -> None:
    paths = get_app_paths(data_dir=tmp_path / "user-data")

    assert paths.root.is_dir()
    assert paths.oauth_token.parent == paths.root / "oauth"
    assert paths.sqlite.parent == paths.root / "database"
    assert paths.digests == paths.root / "digests"
    assert paths.root != Path.cwd()


def test_sensitive_files_are_ignored_by_git() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    for pattern in (".env", "credentials.json", "token*.json", "*.sqlite*", ".venv"):
        assert pattern in gitignore
    assert "!.env.example" in gitignore


def test_required_project_directories_are_present() -> None:
    expected_directories = (
        "src/gmail_mcp/domain",
        "src/gmail_mcp/application",
        "src/gmail_mcp/adapters",
        "src/gmail_mcp/bootstrap",
        "tests/unit",
        "tests/integration",
        "docs/architecture",
    )

    for directory in expected_directories:
        assert Path(directory).is_dir()


def test_secret_redacting_filter_removes_known_secret() -> None:
    filter_ = SecretRedactingFilter(["openai-test-secret"])
    record = logging.LogRecord(
        "gmail_mcp", 20, __file__, 1, "key=%s", ("openai-test-secret",), None
    )

    assert filter_.filter(record) is True
    assert record.getMessage() == "key=[REDACTED]"


def test_secret_redacting_filter_removes_secrets_from_tracebacks() -> None:
    secret = "openai-test-secret"
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    handler.addFilter(SecretRedactingFilter([secret]))
    logger = logging.getLogger("gmail_mcp.test_redaction")
    logger.handlers = [handler]
    logger.propagate = False

    try:
        raise RuntimeError(secret)
    except RuntimeError:
        logger.exception("analysis failed")

    assert secret not in stream.getvalue()
    assert "Exception details redacted." in stream.getvalue()


def test_default_redacting_filter_removes_cached_exception_text() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    handler.addFilter(SecretRedactingFilter())
    record = logging.LogRecord("gmail_mcp", 40, __file__, 1, "analysis failed", (), None)
    record.exc_text = "cached trace: openai-test-secret"

    handler.handle(record)

    assert "openai-test-secret" not in stream.getvalue()
    assert "Exception details redacted." in stream.getvalue()


def test_symlinked_data_directory_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "oauth").symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic links"):
        get_app_paths(data_dir=root)


def test_symlinked_token_permissions_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.touch()
    token = tmp_path / "token.json"
    token.symlink_to(target)

    with pytest.raises(ValueError, match="symbolic link"):
        restrict_file_permissions(token)


def test_gmail_credentials_symlink_is_rejected_before_resolution(tmp_path: Path) -> None:
    target = tmp_path / "credentials-target.json"
    target.write_text("{}", encoding="utf-8")
    credentials = tmp_path / "credentials.json"
    credentials.symlink_to(target)

    with pytest.raises(ConfigurationError, match="regular local credentials"):
        load_gmail_settings(
            environ={"GMAIL_CREDENTIALS_PATH": str(credentials)},
            env_file=tmp_path / "missing.env",
            data_dir=tmp_path / "data",
        )


def test_disconnect_configuration_does_not_require_credentials(tmp_path: Path) -> None:
    settings = load_gmail_settings(
        environ={},
        env_file=tmp_path / "missing.env",
        data_dir=tmp_path / "data",
        require_credentials=False,
    )

    assert settings.credentials_path is None


def test_provider_status_normalizes_selection_and_ignores_whitespace_keys(tmp_path: Path) -> None:
    status = load_provider_status(
        environ={"AI_PROVIDER": " CLAUDE ", "OPENAI_API_KEY": "key", "ANTHROPIC_API_KEY": "  "},
        env_file=tmp_path / "missing.env",
    )

    assert status.selected == "claude"
    assert status.openai_available is True
    assert status.claude_available is False
