# Gmail MCP

Lokalna, rozwijana w Pythonie usługa MCP do prywatnej pracy z Gmailem. Projekt
portfolio pokazuje integrację OAuth 2.0, architekturę heksagonalną i bezpieczne
przygotowanie pod analizę GenAI (OpenAI lub Claude).

> Status: MVP ukończone. Usługa lokalnie odczytuje Gmail, tworzy Digesty,
> udostępnia FastMCP przez `stdio` oraz wykonuje wyłącznie potwierdzone analizy AI.

## Co działa

- Lokalny flow OAuth 2.0 dla jednego aktywnego konta Gmail naraz, uruchamiany w przeglądarce; docelowo lokalne filtry są odseparowane per konto.
- Wyłącznie scope `https://www.googleapis.com/auth/gmail.readonly`.
- Polecenia do połączenia, sprawdzenia statusu i lokalnego odłączenia konta.
- Token OAuth poza repozytorium, w prywatnym katalogu danych użytkownika.
- Ochrona przed symlinkami dla pliku credentials i tokenu oraz ograniczone
  uprawnienia tokenu (`0600` na systemach POSIX).
- Digest wątków Gmail z deduplikacją, lokalnym harmonogramem i retencją danych.
- Serwer FastMCP z dokładnie trzema narzędziami: odczyt Digestu, potwierdzona
  analiza ad hoc oraz świadome porównanie OpenAI i Claude.
- Trzyfazowe potwierdzenie (`preview` → `confirm` → `execute`) przed odczytem
  body wiadomości lub wywołaniem AI; tokeny są krótkotrwałe, opaque i single-use.
- OpenAI lub Claude jako lokalnie wybrany dostawca analizy; porównanie wymaga
  konfiguracji obu dostawców i przekazuje im ten sam oczyszczony tekst.

## Wymagania

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Konto Google oraz projekt Google Cloud z włączonym Gmail API

## Instalacja

```bash
git clone git@github.com:under34/mcp-gmail.git
cd mcp-gmail
uv sync --locked
cp .env.example .env
```

Uruchomienie kontroli jakości:

```bash
uv run pytest -q
uv run ruff check .
```

## Konfiguracja Google OAuth

1. W Google Cloud utwórz lub wybierz projekt.
2. Włącz **Gmail API**.
3. Skonfiguruj ekran zgody OAuth. Dla trybu testowego dodaj własny adres jako
   test user.
4. Utwórz OAuth Client ID typu **Desktop app** i pobierz plik JSON.
5. Zapisz go poza checkoutem, np. `~/secure/gmail-credentials.json`.
6. Ustaw w lokalnym `.env` jego bezwzględną ścieżkę:

```dotenv
GMAIL_CREDENTIALS_PATH=/absolute/path/to/gmail-credentials.json
```

Plik credentials musi być zwykłym plikiem, bez symlinków i poza repozytorium.
Nie dodawaj go do Git.

## Polecenia Gmail

```bash
# Przy braku używalnego tokenu otwiera przeglądarkę i wykonuje lokalny flow OAuth.
uv run gmail-mcp connect-gmail

# Sprawdza zapisane połączenie; nie otwiera przeglądarki.
uv run gmail-mcp gmail-status

# Usuwa wyłącznie lokalny token OAuth. Nie cofa dostępu w Google i nie zmienia maili.
uv run gmail-mcp disconnect-gmail

# Pokazuje liczbę wątków przed zapisem filtra.
uv run gmail-mcp preview-gmail-filter --query 'from:boss@example.com'

# Ponownie sprawdza i zapisuje filtr wyłącznie po jawnym potwierdzeniu.
uv run gmail-mcp set-gmail-filter --query 'label:work' --confirm

# Pokazuje filtr aktywny dla bieżącego konta i stan lokalnego dostawcy AI.
uv run gmail-mcp gmail-filter-status
uv run gmail-mcp ai-provider-status

# Uruchamia ten sam Digest, którego wywołuje lokalny cron.
uv run gmail-mcp run-daily-digest

# Usuwa lokalne wyniki starsze niż 30 dni.
uv run gmail-mcp cleanup-local-data

# Nieodwracalnie usuwa lokalne wyniki aktywnego konta; opcjonalnie także token OAuth.
uv run gmail-mcp delete-local-data --confirm --include-oauth-token

# Uruchamia lokalny serwer MCP wyłącznie przez stdio.
uv run gmail-mcp-server
```

Po poprawnym połączeniu pierwsze polecenie wyświetli adres połączonego konta.
Jeżeli token jest nieważny lub cofnięty, narzędzie zwróci bezpieczny komunikat z
instrukcją ponownego połączenia. `disconnect-gmail` działa także wtedy, gdy
oryginalny plik credentials nie jest już dostępny.

## Zmienne środowiskowe

| Zmienna | Cel |
| --- | --- |
| `GMAIL_CREDENTIALS_PATH` | Wymagany wyłącznie dla `connect-gmail`; ścieżka do pobranego pliku OAuth poza repozytorium. |
| `GMAIL_MCP_DATA_DIR` | Opcjonalne lokalne nadpisanie katalogu danych; musi znajdować się poza checkoutem. |
| `AI_PROVIDER` | Dostawca podsumowań: `openai` (domyślnie) lub `claude`. |
| `OPENAI_API_KEY` | Klucz wymagany, gdy wybrano `openai`; także dla porównania modeli. |
| `ANTHROPIC_API_KEY` | Klucz wymagany, gdy wybrano `claude`; także dla porównania modeli. |
| `DIGEST_SCHEDULE_ENABLED` | `true` (domyślnie) albo `false`; wyłącza cronowy Digest bez zmiany danych. |
| `DIGEST_SCHEDULE_TIME` | Godzina lokalnego crona w formacie `HH:MM`; domyślnie `08:00`. |
| `DIGEST_SCHEDULE_TIMEZONE` | Opcjonalna strefa IANA, np. `Europe/Warsaw`, do dokumentacji i konfiguracji crona. |

Zmienne procesu mają pierwszeństwo przed `.env`. OAuth nie wymaga żadnego klucza
OpenAI ani Anthropic. Analiza ad hoc wymaga klucza wybranego dostawcy, a
porównanie modeli wymaga obu kluczy.

## Lokalny harmonogram

Aplikacja nie zmienia systemowego crontaba. Dodaj lokalnie wpis uruchamiający
CLI zgodnie z `DIGEST_SCHEDULE_TIME`, np. dla 08:00: `0 8 * * * cd /ścieżka/do/mcp-gmail && uv run gmail-mcp run-daily-digest --scheduled`.
Cron powinien mieć dostęp do tych samych zmiennych środowiskowych lub lokalnego
pliku `.env`; zmiana dostawcy albo harmonogramu działa przy następnym uruchomieniu.
Przed każdym rzeczywistym Digestem aplikacja wykonuje lokalną retencję wyników
starszych niż 30 dni.

## Lokalny serwer MCP

`uv run gmail-mcp-server` uruchamia serwer wyłącznie przez transport `stdio`.
Nie otwiera portu HTTP ani nie wykonuje operacji modyfikujących Gmaila.

| Narzędzie | Działanie |
| --- | --- |
| `get_daily_digest` | Zwraca ostatni lokalny Digest aktywnego konta. |
| `summarize_gmail` | Wykonuje potwierdzoną analizę wątków z Aktywnego Filtru lub jednorazowego query. |
| `compare_summaries` | Porównuje OpenAI i Claude dla jednego wątku z Aktywnego Filtru. |

Narzędzia analityczne działają w trzech fazach: preview pokazuje wyłącznie
metadata, confirm pobiera i hashuje oczyszczone body po jawnej zgodzie, a execute
wywołuje AI przy użyciu jednorazowego tokenu. Wszystkie odpowiedzi stosują
envelope `status`, `data`, `reason`, `next_action`.

## Bezpieczeństwo i prywatność

- Aplikacja nie wysyła, nie usuwa ani nie modyfikuje wiadomości Gmail.
- Nie loguje tokenów, kodów OAuth, treści maili ani załączników.
- Token, przyszła baza SQLite i digesty pozostają w lokalnym katalogu danych
  użytkownika (`platformdirs`), poza checkoutem.
- `disconnect-gmail` usuwa tylko lokalny token. Jeśli chcesz cofnąć dostęp po
  stronie Google, zrób to w ustawieniach bezpieczeństwa konta Google.
- Retencja i `delete-local-data` usuwają wyłącznie lokalne dane aplikacji; nie
  zmieniają wiadomości, etykiet ani innych danych w Gmailu. Ręczne usunięcie
  zachowuje aktywny filtr i plik credentials OAuth.
- Usunięcie danych blokuje nowe potwierdzone operacje i bezpiecznie synchronizuje
  się z już aktywnym odczytem; body, prompty i klucze API nie są zapisywane w SQLite.

## Architektura i roadmapa

Kod jest podzielony na warstwy `domain`, `application`, `adapters` i `bootstrap`.
Szczegóły decyzji oraz plan prac znajdują się w
[`_bmad-output/planning-artifacts`](./_bmad-output/planning-artifacts/).

MVP obejmuje Epiki 1–3 i jest ukończone. Następny etap to zaplanowanie Epiku 4
na podstawie potrzeb użytkowników lub rozszerzeń portfolio.

## Licencja

Projekt hobbystyczny/portfolio. Licencja zostanie dodana przed publiczną
dystrybucją.
