from gmail_mcp.application.thread_content import sanitize_thread_text


def test_sanitize_thread_text_removes_signature_and_quoted_history() -> None:
    text = "Aktualna prośba.\n\n-- \nPodpis\n\n> Stara wiadomość"

    assert sanitize_thread_text(text) == "Aktualna prośba."


def test_sanitize_thread_text_removes_forwarded_message_history() -> None:
    text = "Aktualna prośba.\n\n---------- Forwarded message ---------\nFrom: old@example.com"

    assert sanitize_thread_text(text) == "Aktualna prośba."
