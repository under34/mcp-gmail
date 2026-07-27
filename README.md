# Gmail MCP

Lokalna usługa MCP do prywatnych podsumowań Gmaila. MVP nie wysyła ani nie
modyfikuje wiadomości Gmail.

## Start lokalny

Wymagany jest Python 3.12 oraz `uv`.

```bash
uv sync --locked
cp .env.example .env
uv run pytest
uv run ruff check .
```

`OPENAI_API_KEY` i `ANTHROPIC_API_KEY` pozostają wyłącznie w środowisku procesu
lub w lokalnym `.env`; zmienne procesu mają pierwszeństwo. OpenAI jest
domyślnym dostawcą (`AI_PROVIDER=openai`), a Claude wybiera się przez
`AI_PROVIDER=claude`. Aplikacja wymaga tylko klucza wybranego dostawcy.

Późniejszy plik Google `credentials.json` przechowuj poza repozytorium i wskaż
go przez `GMAIL_CREDENTIALS_PATH`. Token OAuth, przyszła baza SQLite i Digesty
trafią do lokalnego katalogu użytkownika (`platformdirs`), a nie do checkoutu.

Nie zapisuj sekretów, treści maili ani załączników w logach.
