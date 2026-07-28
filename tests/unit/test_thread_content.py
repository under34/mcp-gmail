from gmail_mcp.application.thread_content import sanitize_thread_text


def test_sanitize_thread_text_removes_signature_and_quoted_history() -> None:
    text = "Aktualna prośba.\n\n-- \nPodpis\n\n> Stara wiadomość"

    assert sanitize_thread_text(text) == "Aktualna prośba."
