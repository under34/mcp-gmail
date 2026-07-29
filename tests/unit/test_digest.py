from __future__ import annotations

import pytest

from gmail_mcp.domain.digest import Digest


def test_failed_digest_requires_a_safe_reason_and_has_no_items() -> None:
    with pytest.raises(ValueError, match="reason"):
        Digest("run", "account", "failed", "now", None, None, 0, ())
