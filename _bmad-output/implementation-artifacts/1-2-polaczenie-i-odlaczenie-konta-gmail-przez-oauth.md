---
baseline_commit: NO_VCS
---

# Story 1.2: Połączenie i odłączenie konta Gmail przez OAuth

Status: done

## Story

As a właściciel konta Gmail,
I want lokalnie połączyć lub odłączyć swoje konto przez OAuth,
so that aplikacja może bezpiecznie czytać tylko dozwolone wiadomości.

## Kontekst i granice

Historia rozszerza bezpieczny bootstrap z 1.1. MVP obsługuje jedno lokalne konto i wyłącznie odczyt Gmaila. Nie implementuj jeszcze MCP, crona, SQLite, filtrów ani analizy AI.

OAuth nie może wymagać klucza OpenAI ani Claude: obecna funkcja ładowania ustawień wymaga klucza AI, lecz polecenie connect używa tylko konfiguracji Gmaila. Rozdziel konfigurację bazową/Gmail od walidacji AI, zachowując jej dotychczasowe działanie dla późniejszych funkcji AI.

## Acceptance Criteria

1. Given poprawny lokalny plik credentials.json i brak ważnego tokenu, when uruchamiam polecenie połączenia Gmail, then aplikacja otwiera lokalny flow OAuth w przeglądarce, and żąda wyłącznie scope https://www.googleapis.com/auth/gmail.readonly bez hasła użytkownika.
2. Given pomyślna zgoda OAuth, when aplikacja odbiera kod zwrotny na lokalnym adresie, then zapisuje refresh token wyłącznie w katalogu danych użytkownika, and pokazuje połączone konto przez emailAddress z Gmail users.getProfile dla me.
3. Given nieważny, cofnięty lub zablokowany przez administratora token, when narzędzie potrzebuje Gmaila, then zwraca failed z instrukcją ponownego połączenia, and nie zwraca pozornie kompletnego wyniku.
4. Given połączone konto, when uruchamiam odłączenie Gmail, then nowe użycie Gmaila jest blokowane, a lokalny token zostaje usunięty idempotentnie, and nie są usuwane, wysyłane ani modyfikowane wiadomości Gmail.

## Tasks / Subtasks

- [x] Zdefiniować kontrakt połączenia bez Google SDK (AC: 1, 3, 4)
  - [x] Dodać wartości domenowe i typowane błędy połączenia; domain nie importuje bibliotek Google.
  - [x] Dodać Port oraz use cases application dla connect, require-connected i disconnect.
  - [x] Wyniki zawierają complete albo failed, bez tokenów, kodów OAuth i wyjątków SDK.

- [x] Oddzielić konfigurację Gmail/OAuth od konfiguracji AI (AC: 1)
  - [x] Zachować env/.env i pierwszeństwo env.
  - [x] Udostępnić credentials path i AppPaths bez wymagania klucza AI.
  - [x] Walidować, że credentials.json istnieje, jest zwykłym plikiem, nie jest symlinkiem i leży poza checkoutem; błąd nie ujawnia zawartości ani sekretnej ścieżki.
  - [x] Nie zmieniać wyboru dostawcy AI ani jego późniejszej walidacji.

- [x] Zaimplementować adapter OAuth i token store (AC: 1, 2, 3)
  - [x] Scope jest stałą tuple z wyłącznie gmail.readonly; nie pochodzi z CLI, env ani inputu.
  - [x] Dla braku lub nieważności tokenu użyć InstalledAppFlow, local host 127.0.0.1, port 0 i open_browser true.
  - [x] Ważny token wykorzystać bez nowej zgody; expired token odświeżyć tylko z refresh tokenem. Refresh failure, revoked token i Gmail 401/403 dają failed oraz reconnect action.
  - [x] Po sukcesie pobrać emailAddress przez Gmail profile endpoint; nie dodawać scope openid, email ani profile.
  - [x] Token zapisywać atomowo w AppPaths.oauth_token: temp file w tym samym katalogu, tryb 0600 przed replace i no-follow po replace. Tokenu nie logować, nie dodawać do SQLite ani checkoutu.
  - [x] Odrzucać odczyt, zapis i usunięcie tokenu przez symlink.

- [x] Zaimplementować lokalne disconnect i CLI bootstrap (AC: 4)
  - [x] Wystawić lokalne CLI connect-gmail, disconnect-gmail oraz gmail-status; CLI tylko składa zależności i deleguje do use case.
  - [x] Disconnect usuwa wyłącznie lokalny token, jest bezpieczny przy drugim wywołaniu i nie używa revoke ani Gmail write API.
  - [x] Po disconnect require-connected zwraca failed plus reconnect action. Nie wprowadzaj SQLite ani AnalysisRun; blokady per account należą do Story 2.1.

- [x] Dodać testy bez prawdziwego OAuth (AC: 1–4)
  - [x] Testy application używają fake Portów; adapter mockuje flow, refresh Credentials i Gmail profile.
  - [x] Pokryć scope, host loopback, port ephemeral, zapis tokenu tylko w app-data, tryb 0600 na POSIX i zwrócony email.
  - [x] Pokryć brak/zły/symlinkowany credentials file, odmowę consent, refresh failure, revoked token, 401/403 i brak pozornego complete.
  - [x] Pokryć disconnect dwa razy, brak Gmail write calls i odmowę użycia po disconnect.
  - [x] Testy nie otwierają przeglądarki ani nie łączą się z Google; manual smoke w README nie jest częścią CI.

## Dev Notes

### Architektura i bezpieczeństwo

- Hexagonalnie: domain nie importuje SDK; application definiuje use cases i Port; tylko adapter Gmail importuje Google SDK; bootstrap jest jedynym composition root.
- Użyj istniejących Settings credentials path, AppPaths oauth token oraz ochrony plików z Story 1.1. Credentials input pozostaje poza repo i nie jest kopiowany do app-data.
- Logi zawierają wyłącznie status i typ błędu, bez tokenu, authorization URL, callback code, email body oraz surowego wyjątku Google.
- Callback jest loopback-only; nie buduj Flask/HTTP endpointu. Disconnect nie robi remote revocation i nie modyfikuje Gmaila.

### Aktualne informacje techniczne

- Google Gmail Python quickstart używa InstalledAppFlow, local loopback flow oraz scope gmail.readonly. Source: Google Gmail Python quickstart, https://developers.google.com/workspace/gmail/api/quickstart/python
- Google wskazuje Desktop/Installed application jako typ klienta lokalnego OAuth; refresh token odnawia dostęp. Source: Google OAuth 2.0, https://developers.google.com/identity/protocols/oauth2

### Aktualny kod do rozszerzenia

- src/gmail_mcp/bootstrap/settings.py: rozdziel konfigurację OAuth od walidacji AI; env czyta wyłącznie bootstrap.
- src/gmail_mcp/bootstrap/paths.py: token tylko w private oauth path, z ochroną symlinków.
- src/gmail_mcp/bootstrap/logging.py: nie loguj surowych wyjątków Google.
- pyproject i lock już zawierają google-api-python-client 2.198.0 oraz google-auth-oauthlib 1.4.0; nie dodawaj zależności bez konieczności.

### References

- Source: planning-artifacts/epics.md, Story 1.2.
- Source: PRD, FR-1 and NFR-1/NFR-3/NFR-5.
- Source: Architecture Spine, AD-4, AD-5 and AD-10.

## Dev Agent Record

### Agent Model Used

GPT-5.6 Codex

### Debug Log References

- Nie dotyczy — historia została przygotowana przed implementacją.

### Completion Notes List

- Ultimate context engine analysis completed - OAuth developer guide created.
- Zweryfikowano aktualny lokalny flow OAuth Google i kontekst Story 1.1.
- Zaimplementowano domain/application port, adapter OAuth, izolację konfiguracji Gmail i lokalne CLI; pytest: 18 passed, ruff: passed.

### File List

- _bmad-output/implementation-artifacts/1-2-polaczenie-i-odlaczenie-konta-gmail-przez-oauth.md
- src/gmail_mcp/domain/gmail_connection.py
- src/gmail_mcp/application/gmail_connection.py
- src/gmail_mcp/adapters/gmail_oauth.py
- src/gmail_mcp/bootstrap/cli.py
- src/gmail_mcp/bootstrap/settings.py
- pyproject.toml
- tests/unit/test_gmail_connection.py
- tests/unit/test_gmail_oauth.py

## Change Log

- 2026-07-27: Zaimplementowano lokalne OAuth Gmail, bezpieczny token store, disconnect i CLI.
- 2026-07-27: Code review — poprawiono bezpieczeństwo ścieżek OAuth, nieinteraktywny status, reconnect i disconnect; pytest: 28 passed, ruff: passed.
- 2026-07-27: Re-review — poprawiono opcjonalne credentials CLI i odzyskiwanie po uszkodzonym/cofniętym tokenie; pytest: 31 passed, ruff: passed.

### Review Findings

- [x] [Review][Patch] Credentials symlink is accepted after path resolution [src/gmail_mcp/bootstrap/settings.py:92]
- [x] [Review][Patch] Status check can unexpectedly launch an interactive OAuth browser flow [src/gmail_mcp/adapters/gmail_oauth.py:36]
- [x] [Review][Patch] Revoked refresh token makes the advertised reconnect command unusable [src/gmail_mcp/adapters/gmail_oauth.py:23]
- [x] [Review][Patch] Disconnect is blocked when credentials.json is unavailable [src/gmail_mcp/bootstrap/cli.py:19]
- [x] [Review][Patch] Token post-replace chmod can follow a raced symlink [src/gmail_mcp/adapters/gmail_oauth.py:75]
- [x] [Review][Patch] Filesystem errors during disconnect escape the result contract [src/gmail_mcp/adapters/gmail_oauth.py:44]
- [x] [Review][Patch] Optional credentials path is asserted before status and disconnect [src/gmail_mcp/bootstrap/cli.py:23]
- [x] [Review][Patch] Explicit reconnect cannot recover from a corrupt or server-revoked cached token [src/gmail_mcp/adapters/gmail_oauth.py:23]
