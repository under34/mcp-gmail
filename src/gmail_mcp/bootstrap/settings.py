"""Validated local settings, loaded only by the composition root."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

from gmail_mcp.bootstrap.paths import AppPaths, get_app_paths

ProviderName = Literal["openai", "claude"]


class ConfigurationError(ValueError):
    """A safe configuration error that never includes a secret value."""


@dataclass(frozen=True, repr=False)
class Settings:
    """Application settings with secrets deliberately omitted from repr output."""

    ai_provider: ProviderName
    openai_api_key: str | None
    anthropic_api_key: str | None
    credentials_path: Path | None
    paths: AppPaths


@dataclass(frozen=True, repr=False)
class GmailSettings:
    credentials_path: Path | None
    paths: AppPaths


@dataclass(frozen=True)
class ProviderStatus:
    selected: ProviderName
    openai_available: bool
    claude_available: bool


def load_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
    data_dir: Path | None = None,
) -> Settings:
    """Load settings for an AI operation."""
    values = _load_values(environ=environ, env_file=env_file)
    gmail_settings = _load_gmail_settings(values, data_dir=data_dir, require_credentials=False)

    provider = _load_provider(values)
    openai_api_key = values.get("OPENAI_API_KEY")
    anthropic_api_key = values.get("ANTHROPIC_API_KEY")
    _validate_selected_provider(provider, openai_api_key, anthropic_api_key)

    return Settings(
        ai_provider=provider,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        credentials_path=gmail_settings.credentials_path,
        paths=gmail_settings.paths,
    )


def load_gmail_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
    data_dir: Path | None = None,
    require_credentials: bool = True,
) -> GmailSettings:
    """Load only local Gmail/OAuth settings without requiring an AI key."""
    return _load_gmail_settings(
        _load_values(environ=environ, env_file=env_file),
        data_dir=data_dir,
        require_credentials=require_credentials,
    )


def load_provider_status(
    *, environ: Mapping[str, str] | None = None, env_file: Path | None = None
) -> ProviderStatus:
    values = _load_values(environ=environ, env_file=env_file)
    provider = _load_provider(values)
    return ProviderStatus(provider, bool(values.get("OPENAI_API_KEY", "").strip()),
                          bool(values.get("ANTHROPIC_API_KEY", "").strip()))


def _load_values(
    *, environ: Mapping[str, str] | None, env_file: Path | None
) -> dict[str, str]:
    dotenv_path = env_file if env_file is not None else Path.cwd() / ".env"
    values = {key: value for key, value in dotenv_values(dotenv_path).items() if value is not None}
    values.update(dict(os.environ if environ is None else environ))
    return values


def _load_gmail_settings(
    values: Mapping[str, str], *, data_dir: Path | None, require_credentials: bool
) -> GmailSettings:
    credentials_value = values.get("GMAIL_CREDENTIALS_PATH")
    if require_credentials and not credentials_value:
        raise ConfigurationError("GMAIL_CREDENTIALS_PATH is required for Gmail OAuth.")
    configured_credentials_path = (
        Path(credentials_value).expanduser() if credentials_value else None
    )
    if configured_credentials_path and configured_credentials_path.is_symlink():
        raise ConfigurationError("GMAIL_CREDENTIALS_PATH must be a regular local credentials file.")
    credentials_path = (
        configured_credentials_path.resolve() if configured_credentials_path else None
    )
    if credentials_path and not credentials_path.is_file():
        raise ConfigurationError("GMAIL_CREDENTIALS_PATH must be a regular local credentials file.")
    if credentials_path and _inside_project_checkout(credentials_path):
        raise ConfigurationError("GMAIL_CREDENTIALS_PATH must be outside the project checkout.")

    configured_data_dir = values.get("GMAIL_MCP_DATA_DIR")
    configured_path = Path(configured_data_dir).expanduser() if configured_data_dir else None
    try:
        paths = get_app_paths(data_dir or configured_path)
    except ValueError as error:
        raise ConfigurationError(
            "GMAIL_MCP_DATA_DIR must resolve outside the current checkout."
        ) from error
    return GmailSettings(credentials_path=credentials_path, paths=paths)


def _inside_project_checkout(path: Path) -> bool:
    return any(
        (ancestor / ".git").exists() and (ancestor / "pyproject.toml").is_file()
        for ancestor in (path, *path.parents)
    )


def _load_provider(values: Mapping[str, str]) -> ProviderName:
    provider = values.get("AI_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "claude"}:
        raise ConfigurationError("AI_PROVIDER must be either 'openai' or 'claude'.")
    return provider


def _validate_selected_provider(
    provider: ProviderName,
    openai_api_key: str | None,
    anthropic_api_key: str | None,
) -> None:
    required_variable = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    selected_key = openai_api_key if provider == "openai" else anthropic_api_key
    if not selected_key or not selected_key.strip():
        raise ConfigurationError(
            f"{required_variable} is required for the selected AI_PROVIDER. "
            "Add it to the process environment or local .env file."
        )
