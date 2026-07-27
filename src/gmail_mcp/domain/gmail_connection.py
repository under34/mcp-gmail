from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConnectionStatus = Literal["complete", "failed"]


@dataclass(frozen=True)
class ConnectionResult:
    status: ConnectionStatus
    email_address: str | None = None
    reason: str | None = None
    next_action: str | None = None

    @classmethod
    def complete(cls, email_address: str | None = None) -> ConnectionResult:
        return cls(status="complete", email_address=email_address)

    @classmethod
    def failed(cls, reason: str, next_action: str) -> ConnectionResult:
        return cls(status="failed", reason=reason, next_action=next_action)
