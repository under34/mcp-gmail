"""Logging helpers that prevent accidental exposure of known secrets."""

from __future__ import annotations

import logging
from collections.abc import Iterable


class SecretRedactingFilter(logging.Filter):
    """Replace configured secret values before a log record is formatted."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.getMessage())
        record.args = ()
        if record.exc_info or record.exc_text:
            record.exc_info = None
            record.exc_text = "Exception details redacted."
        if record.stack_info:
            record.stack_info = "Stack details redacted."
        return True

    def _redact(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, "[REDACTED]")
        return value


def configure_logging(*, secrets: Iterable[str] = ()) -> logging.Logger:
    """Return the application logger with a secret-redaction filter attached."""
    logger = logging.getLogger("gmail_mcp")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    for handler in logger.handlers:
        handler.addFilter(SecretRedactingFilter(secrets))
    return logger
