from __future__ import annotations

import re


def sanitize_thread_text(text: str) -> str:
    """Remove common signatures and quoted replies before an AI request."""
    without_signature = re.split(r"\n--\s*\n", text, maxsplit=1)[0]
    lines = [line for line in without_signature.splitlines() if not line.lstrip().startswith(">")]
    without_reply = re.split(
        r"\n(?:On .+ wrote:|-{2,}\s*(?:Forwarded message|Original Message)\s*-{2,}|"
        r"From:\s+.+\n(?:Sent|Date):\s+.+\n(?:To|Subject):)",
        "\n".join(lines),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return "\n".join(line.strip() for line in without_reply.splitlines() if line.strip())
