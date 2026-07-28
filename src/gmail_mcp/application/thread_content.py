from __future__ import annotations

import re


def sanitize_thread_text(text: str) -> str:
    """Remove common signatures and quoted replies before an AI request."""
    without_signature = re.split(r"\n--\s*\n", text, maxsplit=1)[0]
    lines = [line for line in without_signature.splitlines() if not line.lstrip().startswith(">")]
    without_reply = re.split(r"\nOn .+ wrote:\s*\n", "\n".join(lines), maxsplit=1)[0]
    return "\n".join(line.strip() for line in without_reply.splitlines() if line.strip())
